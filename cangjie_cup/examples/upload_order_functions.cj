// 上传修复示例：数量范围1至1000，单价范围0至1000000。
// 合法订单费用为数量乘单价，非法订单返回-1。
public func validQuantity(quantity: Int64): Bool {
    quantity >= 0 && quantity <= 1000
}

public func fee(quantity: Int64, unitPrice: Int64): Int64 {
    if (!validQuantity(quantity)) {
        return -1
    }
    if (unitPrice < 0 || unitPrice > 1000000) {
        return -1
    }
    return quantity + unitPrice
}
