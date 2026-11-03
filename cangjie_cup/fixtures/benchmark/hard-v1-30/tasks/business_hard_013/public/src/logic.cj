package bench

public func hard013(amount: Int64, rate: Int64, floor: Int64, ceiling: Int64): Int64 {
    var fee = (amount * rate + 9999) / 10000
    if (fee < floor) { fee = floor }
    if (fee > ceiling) { fee = ceiling }
    return fee
}
