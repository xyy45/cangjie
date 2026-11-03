package crossstock

public func processStock(stock: Int64, requested: Int64): Int64 {
    if (stock < 0 || stock > 1000 || !canFulfill(stock, requested)) { return -1 }
    return remainingStock(stock, requested)
}
