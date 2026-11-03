package bench

import std.unittest.*
import std.unittest.testmacro.*

@Test
class UploadedTests {
    @TestCase
    func case0() {
        @Expect(refundTotal([300, -100], 1000), 200)
    }
    @TestCase
    func case1() {
        @Expect(refundTotal([500, 500], 1000), 1000)
    }
    @TestCase
    func case2() {
        @Expect(refundTotal([], 1000), 0)
    }
    @TestCase
    func case3() {
        @Expect(refundTotal([], 0), 0)
    }
}
