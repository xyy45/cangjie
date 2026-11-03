package bench

public func hard009(quantity: Int64, price: Int64, member: Bool): Int64 {
    if (!valid009(quantity, price) && !member) { return -1 }
    let amount = amount009(quantity, price)
    if (member) { return amount }
    return amount + 20
}
