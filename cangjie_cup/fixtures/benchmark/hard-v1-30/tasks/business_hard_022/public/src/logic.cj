package bench

public func hard022(amount: Int64, percent: Int64, threshold: Int64, coupon: Int64): Int64 {
    var value = amount * percent / 100
    if (value >= threshold) { value = value - coupon }
    return value
}
