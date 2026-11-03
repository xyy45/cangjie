package bench

public func hard019(quantity: Int64, price: Int64, member: Bool): Int64 {
    if (!valid019(quantity, price)) { return -1 }
    let amount = amount019(quantity, price)
    if (member) { return amount }
    return amount + 20
}
