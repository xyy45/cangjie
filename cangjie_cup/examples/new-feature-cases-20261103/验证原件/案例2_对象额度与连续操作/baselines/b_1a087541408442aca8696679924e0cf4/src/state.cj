package bench

public struct QuotaState {
    public let available: Int64
    public let reserved: Int64
    public init(available: Int64, reserved: Int64) {
        this.available = available
        this.reserved = reserved
    }
    public func total(): Int64 { this.available + this.reserved }
}
