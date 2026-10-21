func netPrice(amount: Int64, discount: Int64): Int64 {
    let charge = amount - discount
    let finalAmount = charge + 7
    return finalAmount
}
main(): Int64 {
    println(netPrice(120, 20))
    return 0
}
