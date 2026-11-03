package bench

public func hard016(amount: Int64, coupon: Int64, threshold: Int64, vip: Bool): Int64 {
    var net = amount - coupon
    if (net < 0) { net = 0 }
    if (vip || net >= threshold) { return net }
    return net + 800
}
