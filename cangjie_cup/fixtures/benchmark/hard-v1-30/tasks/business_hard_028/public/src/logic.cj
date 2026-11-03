package bench

public func hard028(quantity: Int64, price: Int64): Int64 {
    if (price < 0) { return -1 }
    if (quantity < 0) { return -quantity * price }
    if (price > 0 && quantity > 9223372036854775807 / price) { return -1 }
    return quantity * price
}
