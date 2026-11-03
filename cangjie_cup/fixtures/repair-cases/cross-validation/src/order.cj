package crossvalidation

// -1 denotes an invalid order; all valid totals are nonnegative.
public func processOrder(quantity: Int64, unitPrice: Int64): Int64 {
    if (!validQuantity(quantity) || unitPrice < 0 || unitPrice > 1000000) {
        return -1
    }
    calculateFee(quantity, unitPrice)
}

