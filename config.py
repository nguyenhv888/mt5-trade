# Cấu hình các mã
symbols = {
    "XAU": "XAUUSD",
    "BTC": "BTCUSD",
    "OIL": "USOIL"
}

order_types = {
    "B": 0,
    "S": 1,
    "BL": 2,
    "SL": 3,
    "BS": 4,
    "SS": 5
}

# Cấu hình loại giao dịch
BUY = "B" # Buy
SELL = "S" # sell
BUY_LIMIT = "BL" # buy limit
SELL_LIMIT = "SL" # sell limit
BUY_STOP = "BS" #buy stop
SELL_STOP = "SS" # sell stop

# Cấu hình loại giao dịch
CLOSE = "CL" #close
CLOSE_PENDING = "CLP" #close pending
ENTRY_SL = "E" #edit stoplot
EDIT_SL = "ESL" #edit stoplot
EDIT_TP = "ETP" # edit tp
GET = "GET"
GET_ORDERS = "GETO" # lấy all lệnh hiện tại
GET_DAILY = "GETD" # Lấy lãi lỗ hôm nay
GET_MONEY = "MONEY"

VOLUME = 0.01