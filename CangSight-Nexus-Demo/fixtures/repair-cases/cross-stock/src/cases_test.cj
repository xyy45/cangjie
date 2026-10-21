package crossstock

import std.unittest.*
import std.unittest.testmacro.*

@Test
class InventoryTests {
    @TestCase
    func zeroRequest() {
        @Expect(canFulfill(5, 0), false)
    }

    @TestCase
    func subtract() {
        @Expect(remainingStock(5, 2), 3)
    }

    @TestCase
    func negativeRequest() {
        @Expect(canFulfill(5, -1), false)
    }

    @TestCase
    func excess() {
        @Expect(canFulfill(5, 6), false)
    }

    @TestCase
    func exact() {
        @Expect(canFulfill(5, 5), true)
    }

    @TestCase
    func normal() {
        @Expect(processStock(5, 2), 3)
    }

    @TestCase
    func empty() {
        @Expect(processStock(0, 1), -1)
    }

    @TestCase
    func exactRemaining() {
        @Expect(processStock(5, 5), 0)
    }

    @TestCase
    func invalidStock() {
        @Expect(processStock(-1, 1), -1)
    }

}
