import MetaTrader5 as mt5
from telethon import TelegramClient, events
from datetime import datetime, timedelta
import config
import logging

# Cấu hình logging
logging.basicConfig(level=logging.INFO)

# Cấu hình Telegram
API_ID = "17442352"
API_HASH = "2954f927fdb47a6783874cf3c21e67ce"
PRIVATE_CHANNEL_LINK = "https://t.me/+yzWYZh8wjc5kYTZl"  # Channel tín hiệu

# Khởi tạo client Telegram
client = TelegramClient("ThanhVan", API_ID, API_HASH)

async def send_message(message):
    """Gửi tin nhắn đến channel lỗi."""
    try:
        channel = await client.get_entity("https://t.me/+QI1UT9w4gqk1NzE1")
        await client.send_message(channel.id, message)
    except Exception as e:
        logging.error(f"Error sending message: {e}")


def ensure_mt5_initialized():
    """Kiểm tra và khởi tạo kết nối MT5 nếu chưa được khởi tạo."""
    if not mt5.initialize():
        return False
    return True


async def close_orders(symbol):
    """Đóng tất cả các lệnh cho symbol và báo cáo tổng lãi/lỗ."""
    if not ensure_mt5_initialized():
        await send_message("Lỗi kết nối MT5")
        return False

    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        await send_message(f"Không có lệnh nào cho mã {symbol}.")
        return False

    total_profit = 0
    for pos in positions:
        total_profit += pos.profit
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": pos.volume,
            "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": pos.ticket,
            "deviation": 10,
            "magic": 0,
            "comment": "Close order",
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            await send_message(f"Lỗi đóng lệnh {pos.ticket}: {result.comment}")
            return False

    await send_message(f"Đã đóng tất cả lệnh cho {symbol}. Tổng lãi/lỗ: {total_profit:.2f}")
    return True

async def close_pending_orders(symbol):
    if not ensure_mt5_initialized():
        await send_message("Lỗi kết nối MT5")
        return False

    # Lấy danh sách lệnh chờ
    pending_orders = mt5.orders_get(symbol=symbol)
    if not pending_orders:
        await send_message(f"Không có lệnh chờ nào cho {symbol}.")
        return False

    # Hủy từng lệnh chờ
    for order in pending_orders:
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": order.ticket,  # ID của lệnh chờ
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            await send_message(f"Lỗi hủy lệnh chờ {order.ticket}: {result.comment}")
            return False

    await send_message(f"Đã hủy tất cả lệnh chờ cho {symbol}.")
    return True

async def modify_orders_by_symbol(symbol, stop_loss=None, take_profit=None):
    """Chỉnh sửa SL hoặc TP của các lệnh cho symbol."""
    if not ensure_mt5_initialized():
        await send_message("Lỗi kết nối MT5")
        return False

    positions = mt5.positions_get(symbol=symbol)
    if positions is None or len(positions) == 0:
        await send_message(f"Không có lệnh nào với symbol {symbol}.")
        return False

    success_count = 0
    for order in positions:
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": order.ticket,
            "sl": stop_loss if stop_loss is not None else order.sl,
            "tp": take_profit if take_profit is not None else order.tp,
        }
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            success_count += 1
            await send_message(f"Đã chỉnh sửa lệnh {order.ticket} ({symbol}): SL={stop_loss}, TP={take_profit}.")
        else:
            await send_message(f"Lỗi chỉnh sửa lệnh {order.ticket}: {result.comment}")

    return success_count > 0


async def close_partial_order(symbol, ticket, volume):
    """Đóng một phần lệnh theo ticket và báo cáo lãi/lỗ."""
    if not ensure_mt5_initialized():
        await send_message("Lỗi kết nối MT5")
        return False

    orders = mt5.positions_get(ticket=ticket)
    if orders is None or len(orders) == 0:
        await send_message(f"Không tìm thấy lệnh {ticket}.")
        return False

    order = orders[0]
    if volume > order.volume:
        await send_message("Khối lượng đóng lớn hơn khối lượng lệnh.")
        return False

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_SELL if order.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
        "position": ticket,
        "deviation": 10,
        "magic": 0,
        "comment": "Partial close",
    }
    
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        await send_message(f"Lỗi đóng một phần lệnh {ticket}: {result.comment}")
        return False

    await send_message(f"Đã đóng một phần {volume} của lệnh {ticket} ({symbol}). Lãi/lỗ: {order.profit:.2f}")
    return True


async def open_market_order(symbol, volume, order_type, stop_loss=None, take_profit=None):
    """Mở lệnh thị trường tại giá hiện tại."""
    if not ensure_mt5_initialized():
        await send_message("Lỗi kết nối MT5")
        return False

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        await send_message(f"Không lấy được thông tin tick cho {symbol}.")
        return False
    price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
    if take_profit is None:
        if stop_loss is None:
            await send_message("Vui lòng cung cấp stop_loss để tính toán take_profit.")
            return False
        if order_type == mt5.ORDER_TYPE_BUY:
            take_profit = price + (price - stop_loss) * 2
        elif order_type == mt5.ORDER_TYPE_SELL:
            take_profit = price - (stop_loss - price) * 2

    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": stop_loss,
        "tp": take_profit,
        "deviation": 10,
        "magic": 0,
        "comment": "Market order",
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        await send_message(f"Lỗi mở lệnh: {result.comment} ")
        return False

    await send_message(f"Đã mở lệnh {order_type} {volume} lot cho {symbol} tại {price}.")
    return True


async def open_pending_order(symbol, volume, order_type, price, stop_loss=None, take_profit=None):
    """Mở lệnh chờ với giá chỉ định."""
    if not ensure_mt5_initialized():
        await send_message("Lỗi kết nối MT5")
        return False
    
    if take_profit is None:
        if stop_loss is None:
            await send_message("Vui lòng cung cấp stop_loss để tính toán take_profit.")
            return False
        if order_type == mt5.ORDER_TYPE_BUY_LIMIT or order_type == mt5.ORDER_TYPE_BUY_STOP:
            take_profit = price + (price - stop_loss) * 2
        elif order_type == mt5.ORDER_TYPE_SELL_LIMIT or order_type == mt5.ORDER_TYPE_SELL_STOP:
            take_profit = price - (stop_loss - price) * 2

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": stop_loss,
        "tp": take_profit,
        "deviation": 10,
        "magic": 0,
        "comment": "Pending order",
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        await send_message(f"Lỗi mở lệnh chờ: {result.comment}")
        return False

    await send_message(f"Đã mở lệnh chờ {order_type} {volume} lot cho {symbol} tại {price}.")
    return True


async def get_open_orders():
    """Lấy danh sách các lệnh đang mở và lệnh chờ, báo cáo lãi/lỗ."""
    if not ensure_mt5_initialized():
        await send_message("Lỗi kết nối MT5")
        return []

    positions = mt5.positions_get()  # Lấy lệnh đang mở
    orders = mt5.orders_get()  # Lấy lệnh chờ

    if (positions is None or len(positions) == 0) and (orders is None or len(orders) == 0):
        await send_message("Hiện không có lệnh nào đang mở hoặc đang chờ.")
        return []

    message = "📊 **Danh sách lệnh đang mở và lệnh chờ:**\n"

    # Hiển thị các lệnh đang mở
    if positions:
        message += "\n🔥 **Lệnh đang mở:**\n"
        for pos in positions:
            message += f"🔹 Lệnh {pos.ticket} - {pos.symbol}: {pos.volume} lot, Lãi/Lỗ {pos.profit:.2f}\n"

    # Hiển thị các lệnh chờ
    if orders:
        message += "\n⏳ **Lệnh chờ:**\n"
        for order in orders:
            order_type = "BUY LIMIT" if order.type == mt5.ORDER_TYPE_BUY_LIMIT else \
                         "SELL LIMIT" if order.type == mt5.ORDER_TYPE_SELL_LIMIT else \
                         "BUY STOP" if order.type == mt5.ORDER_TYPE_BUY_STOP else \
                         "SELL STOP" if order.type == mt5.ORDER_TYPE_SELL_STOP else "UNKNOWN"
            message += f"🔹 Lệnh {order.ticket} - {order.symbol}: {order.volume} lot, Loại {order_type}, Giá {order.price:.5f}\n"

    await send_message(message)
    return {"positions": positions, "orders": orders}


async def check_open_orders(symbol):
    """Kiểm tra có lệnh mở hoặc lệnh chờ nào cho symbol không và trả về số volume đã vào nếu chưa đủ."""
    if not ensure_mt5_initialized():
        await send_message("Lỗi kết nối MT5")
        return 0

    # Lấy danh sách lệnh mở
    positions = mt5.positions_get(symbol=symbol)
    open_volume = sum(pos.volume for pos in positions) if positions else 0

    # Lấy danh sách lệnh chờ
    pending_orders = mt5.orders_get(symbol=symbol)
    pending_volume = sum(order.volume_initial for order in pending_orders) if pending_orders else 0

    # Tổng khối lượng đã vào (cả lệnh mở và lệnh chờ)
    total_volume = open_volume + pending_volume

    # Nếu tổng volume chưa đủ, trả về số volume đã vào, nếu đủ thì trả về 0
    return total_volume

async def get_daily_profit():
    """Lấy tổng lãi/lỗ trong ngày, bao gồm phí sàn và swap."""
    
    # Đảm bảo kết nối với MT5
    if not ensure_mt5_initialized():
        await send_message("Lỗi kết nối MT5")
        return 0.0
    
    # Xác định thời gian đầu ngày và cuối ngày
    start_of_day = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)  # Lấy đến cuối ngày

    # Lấy danh sách giao dịch trong ngày
    history_orders = mt5.history_deals_get(start_of_day, end_of_day)

    # Kiểm tra nếu không có giao dịch
    if history_orders is None or len(history_orders) == 0:
        await send_message("📉 Không có giao dịch nào trong ngày.")
        return 0.0

    # Tính tổng lợi nhuận/thua lỗ bao gồm phí sàn và swap
    total_profit = sum(deal.profit + deal.commission + deal.swap for deal in history_orders)

    # Gửi tin nhắn báo cáo
    message = f"📊 Tổng lãi/lỗ trong ngày: {total_profit:.2f} USD (Đã tính phí & swap)"
    await send_message(message)

    return total_profit

async def move_sl_to_entry(symbol):
    """Dời Stop Loss (SL) về điểm vào lệnh (Entry) cho tất cả các lệnh mở của một symbol."""
    if not ensure_mt5_initialized():
        await send_message("Lỗi kết nối MT5")
        return False

    # Lấy danh sách lệnh mở của symbol
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        await send_message(f"Không có lệnh nào mở cho {symbol}.")
        return False

    updated_count = 0  # Đếm số lệnh được cập nhật

    for pos in positions:
        entry_price = pos.price_open  # Giá vào lệnh
        current_sl = pos.sl  # Stop Loss hiện tại

        # Nếu SL đã bằng Entry thì bỏ qua
        if current_sl == entry_price:
            continue  

        # Tạo yêu cầu cập nhật SL
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,  # ID của lệnh cần cập nhật
            "sl": entry_price,  # Cập nhật Stop Loss về Entry
            "tp": pos.tp,  # Giữ nguyên Take Profit
        }
        result = mt5.order_send(request)

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            updated_count += 1
        else:
            await send_message(f"Lỗi dời SL lệnh {pos.ticket}: {result.comment}")

    if updated_count > 0:
        await send_message(f"Đã dời SL về Entry cho {updated_count} lệnh của {symbol}.")
    else:
        await send_message(f"Không có lệnh nào cần dời SL cho {symbol}.")
    
    return True

async def get_current_price(symbol):
    """Lấy giá Bid và Ask hiện tại của một symbol và gửi tin nhắn."""
    if not ensure_mt5_initialized():
        await send_message("Lỗi kết nối MT5")
        return

    # Lấy thông tin giá của symbol
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        await send_message(f"Lỗi lấy giá cho {symbol}. Có thể symbol không tồn tại hoặc chưa được kích hoạt.")
        return

    # Kiểm tra nếu tick.last hợp lệ
    last_price = f"{tick.last:.5f}" if tick.last is not None and tick.last != 0 else "Không có"

    message = (
        f"📈 Giá hiện tại của {symbol}:\n"
        f"🔹 Bid: {tick.bid:.5f}\n"
        f"🔹 Ask: {tick.ask:.5f}\n"
        f"🔹 Last: {last_price}"
    )

    await send_message(message)

async def get_account_balance():
    """Lấy số dư tài khoản và gửi tin nhắn."""
    if not ensure_mt5_initialized():
        await send_message("Lỗi kết nối MT5")
        return

    # Lấy thông tin tài khoản
    account_info = mt5.account_info()
    if account_info is None:
        await send_message("Lỗi lấy thông tin tài khoản. Kiểm tra kết nối MT5.")
        return

    message = (
        f"💰 **Thông tin tài khoản** 💰\n"
        f"🔹 Số dư (Balance): {account_info.balance:.2f}\n"
    )

    await send_message(message)

async def handle_message(event):
    """Xử lý tin nhắn nhận từ kênh Telegram."""
    message_text = event.message.message.lower()
    parts = message_text.split()
    if not parts:
        return

    command = parts[0].upper()
    try:
        # Lệnh lấy danh sách các lệnh đang mở
        if command == config.GET_ORDERS:
            await get_open_orders()

        elif command == config.GET_DAILY:
            await get_daily_profit()
        elif command == config.GET_MONEY:
            await get_account_balance()

        # Các lệnh cần symbol làm tham số thứ 2
        elif len(parts) >= 2:
            symbol_key = parts[1].upper()
            if symbol_key not in config.symbols:
                symbol = symbol_key
            else:
                symbol = config.symbols[symbol_key]

            if command == config.GET and len(parts) == 2:
                await get_current_price(symbol)
            elif command == config.ENTRY_SL and len(parts) == 2:
                await move_sl_to_entry(symbol)
            elif command == config.CLOSE and len(parts) == 2:
                await close_orders(symbol)
            elif command == config.CLOSE_PENDING and len(parts) == 2:
                await close_pending_orders(symbol)
            elif command == config.EDIT_SL and len(parts) == 3:
                value = float(parts[2])
                await modify_orders_by_symbol(symbol, stop_loss=value)

            elif command == config.EDIT_TP and len(parts) == 3:
                value = float(parts[2])
                await modify_orders_by_symbol(symbol, take_profit=value)

            elif command in [config.BUY, config.SELL]:
                vol = config.VOLUME - await check_open_orders(symbol)
                if vol == 0:
                    await send_message(f"Có lệnh {symbol} rồi, không vào nữa!")
                    return
                order_type = config.order_types[command]
                if len(parts) == 2:
                    await open_market_order(symbol, vol, order_type)
                elif len(parts) == 3:
                    sl = float(parts[2])
                    await open_market_order(symbol, vol, order_type, stop_loss=sl)
                elif len(parts) == 4:
                    sl = float(parts[2])
                    tp = float(parts[3])
                    await open_market_order(symbol, vol, order_type, stop_loss=sl, take_profit=tp)

            elif command in [config.BUY_LIMIT, config.BUY_STOP, config.SELL_LIMIT, config.SELL_STOP]:
                vol = config.VOLUME - await check_open_orders(symbol)
                if vol == 0:
                    await send_message(f"Có lệnh {symbol} rồi, không vào nữa!")
                    return
                order_type = config.order_types[command]
                if len(parts) == 4:
                    price = float(parts[2])
                    sl = float(parts[3])
                    await open_pending_order(symbol, vol, order_type, price, stop_loss=sl)
                elif len(parts) == 5:
                    price = float(parts[2])
                    sl = float(parts[3])
                    tp = float(parts[4])
                    await open_pending_order(symbol, vol, order_type, price, stop_loss=sl, take_profit=tp)
                else:
                    await send_message(f"❌ Số tham số không hợp lệ cho lệnh chờ: {message_text}")

            else:
                await send_message(f"❌ Không hiểu lệnh: {message_text}")
        else:
            await send_message(f"❌ Không hiểu lệnh: {message_text}")
    except Exception as e:
        await send_message(f"⚠️ Lỗi xử lý tin nhắn: {str(e)}")


async def main():
    """Chạy bot Telegram."""
    await client.start()
    logging.info("Đã kết nối đến Telegram.")

    @client.on(events.NewMessage(chats=PRIVATE_CHANNEL_LINK))
    async def new_message_listener(event):
        await handle_message(event)

    await client.run_until_disconnected()


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
