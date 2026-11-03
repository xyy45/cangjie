package bench

public func hard010(quantity: Int64, cap: Int64): Int64 {
    var total = quantity
    if (quantity > 100) { total = quantity * 2 }
    if (quantity > 200) { total = quantity * 3 }
    if (total > cap) { return cap }
    return total
}
