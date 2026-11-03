package orderprice

public func validPrice(price: Int64): Bool {
    price >= 0 && price < 1000000
}
