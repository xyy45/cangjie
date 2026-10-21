package crossdiscount

public func discountFor(amount: Int64): Int64 {
    if (amount < 0) { return -1 }
    if (amount > 100) { return 10 }
    return 0
}
