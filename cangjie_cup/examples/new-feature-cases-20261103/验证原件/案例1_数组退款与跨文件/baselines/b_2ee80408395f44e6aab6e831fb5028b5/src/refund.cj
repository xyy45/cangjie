package bench

public func refundTotal(refunds: Array<Int64>, paid: Int64): Int64 {
    if (paid < 0 || paid > 10000000) { return -1 }
    let total = netRefund(refunds)
    if (total < 0 || total >= paid) { return -1 }
    return total
}
