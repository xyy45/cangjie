package bench

public func hard012(amount: Int64, percent: Int64, threshold: Int64, coupon: Int64): Int64 {
    var value = amount * percent / 100
    if (value >= threshold) { value = value - coupon }
    if (value < 0) { value = 0 }
    return value
}
