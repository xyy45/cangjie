package bench

public func hard024(stock: Int64, reserved: Int64, quantity: Int64, release: Bool): Int64 {
    if (quantity <= 0) { return stock }
    if (release) {
        if (quantity > reserved) { return stock }
        return stock + quantity
    }
    if (quantity > stock) { return stock }
    return stock - quantity
}
