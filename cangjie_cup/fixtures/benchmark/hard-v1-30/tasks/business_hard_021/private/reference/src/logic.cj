package bench

public func hard021(paid: Int64, refunded: Int64, requested: Int64): Int64 {
    if (refunded > paid) { return -1 }
    if (requested <= 0 || requested > paid - refunded) { return -1 }
    return refunded + requested
}
