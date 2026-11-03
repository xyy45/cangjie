package bench

public func hard007(points: Int64, amount: Int64, requested: Int64, percent: Int64): Int64 {
    let balance = points / 100
    let cap = amount * percent / 100
    var used = requested
    if (used > balance) { used = balance }
    if (used > cap) { used = cap }
    return used
}
