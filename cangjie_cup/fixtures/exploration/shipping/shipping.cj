// Weight is grams; distance is kilometers; returned fee is cents.
public func ceilDiv(value: Int64, divisor: Int64): Int64 {
    return (value + divisor - 1) / divisor
}

public func shippingFee(weight: Int64, distance: Int64, express: Bool): Int64 {
    if (weight < 1 || weight > 30000 || distance < 1 || distance > 2000) {
        return -1
    }
    var fee: Int64 = 800
    if (weight > 1000) {
        fee = fee + ((weight - 1000) / 500) * 200
    }
    if (distance >= 500) {
        fee = fee + 300
    }
    if (express) {
        fee = fee + 500
    }
    return fee
}
