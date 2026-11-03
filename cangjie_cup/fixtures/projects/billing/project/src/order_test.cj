package billing

import std.unittest.*
import std.unittest.testmacro.*

@Test
class BillingTests {
    @TestCase
    func amount() {
        @Expect(total(2), 102)
    }

    @TestCase
    func zero() {
        @Expect(fee(0), 0)
    }
}
