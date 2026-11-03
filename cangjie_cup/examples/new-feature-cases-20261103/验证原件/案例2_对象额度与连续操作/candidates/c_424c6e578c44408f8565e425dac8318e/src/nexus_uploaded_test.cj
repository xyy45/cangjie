package bench

import std.unittest.*
import std.unittest.testmacro.*

private let __nexusObjectTarget: (QuotaState, String) -> QuotaState = applyQuota
private func __nexusObjectCtor0(__nexusCtorField0: Int64, __nexusCtorField1: Int64): QuotaState { return QuotaState(__nexusCtorField0, __nexusCtorField1) }

@Test
class UploadedTests {
    @TestCase
    func case0() {
        let __nexusObjectActual0: QuotaState = __nexusObjectTarget(__nexusObjectCtor0(20, 0), "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
        @Expect(__nexusObjectActual0.available, 10)
        @Expect(__nexusObjectActual0.reserved, 10)
    }
    @TestCase
    func case1() {
        let __nexusObjectActual1: QuotaState = __nexusObjectTarget(__nexusObjectCtor0(10, 0), "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
        @Expect(__nexusObjectActual1.available, 10)
        @Expect(__nexusObjectActual1.reserved, 0)
    }
}
