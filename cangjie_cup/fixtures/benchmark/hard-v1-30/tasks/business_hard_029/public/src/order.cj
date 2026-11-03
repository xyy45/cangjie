package bench

public func hard029(quantity: Int64, price: Int64, member: Bool): Int64 {
    if (!valid029(quantity, price)) { return -1 }
    let amount = amount029(quantity, price)
    if (member) { return amount }
    return amount + 20
}
