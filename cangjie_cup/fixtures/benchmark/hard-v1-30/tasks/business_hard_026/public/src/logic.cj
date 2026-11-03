package bench

public func hard026(amount: Int64, coupon: Int64, threshold: Int64, vip: Bool): Int64 {
    let net = amount - coupon
    if (vip || net >= threshold) { return net }
    return net + 800
}
