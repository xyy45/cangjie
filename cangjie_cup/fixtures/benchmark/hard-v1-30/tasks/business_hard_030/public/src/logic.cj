package bench

public func hard030(quantity: Int64, cap: Int64): Int64 {
    var total = quantity
    if (quantity > 100) { total = 100 + (quantity - 100) * 2 }
    if (quantity > 200) { total = 300 + (quantity - 200) * 3 }
    return total
}
