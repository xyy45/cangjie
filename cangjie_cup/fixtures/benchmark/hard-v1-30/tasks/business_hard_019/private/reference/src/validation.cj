package bench

public func valid019(quantity: Int64, price: Int64): Bool {
    return quantity >= 1 && quantity <= 1000 && price >= 1 && price <= 10000
}
