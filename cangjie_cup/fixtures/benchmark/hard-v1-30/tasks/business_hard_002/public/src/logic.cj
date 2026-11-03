package bench

public func hard002(amount: Int64, percent: Int64, threshold: Int64, coupon: Int64): Int64 {
    var value = amount
    if (value >= threshold) { value = value - coupon }
    if (value < 0) { value = 0 }
    return value * percent / 100
}
