package bench

public func hard003(amount: Int64, rate: Int64, floor: Int64, ceiling: Int64): Int64 {
    if (amount == 0) { return 0 }
    var fee = (amount * rate + 9999) / 10000
    if (fee < floor) { fee = floor }
    if (fee > ceiling) { fee = ceiling }
    return fee
}
