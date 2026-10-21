package crossdiscount

public func checkoutTotal(amount: Int64): Int64 {
    if (amount < 0) { return -1 }
    return amount + discountFor(amount)
}
