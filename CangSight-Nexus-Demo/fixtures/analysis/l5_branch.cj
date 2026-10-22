func shipping(amount: Int64, member: Bool): Int64 {
    var fee: Int64 = 800
    if (amount >= 9900) {
        fee = 0
    }
    if (member && amount >= 5000) {
        fee = 0
    }
    return fee
}
main(): Int64 {
    println(shipping(6000, true))
    return 0
}
