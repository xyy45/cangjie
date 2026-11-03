package bench

public func netRefund(refunds: Array<Int64>): Int64 {
    var total: Int64 = 0
    var index: Int64 = 0
    while (index < refunds.size) {
        let amount = refunds[index]
        if (amount > 0) {
            total = total + amount
        }
        index = index + 1
    }
    return total
}

// local defect validation
