package bench
import std.core.println as __nexusSeqPrint2c8c3115d95a9761
import std.unittest.*
import std.unittest.testmacro.*
private let __nexusV4Bound2c8c3115d95a9761: (QuotaState, String) -> QuotaState = applyQuota
private func __nexusObjectCtor0(__nexusCtorField0: Int64, __nexusCtorField1: Int64): QuotaState { return QuotaState(__nexusCtorField0, __nexusCtorField1) }

@Test
class NexusSequencesV42c8c3115d95a9761 {
private func __nexusObjectEncode2c8c3115d95a9761(__nexusObjectValue: QuotaState): String {
var __nexusObjectWire = "o:QuotaState:2:"
let __nexusObjectFieldWire0 = "${__nexusObjectValue.available}"
__nexusObjectWire = __nexusObjectWire + "${__nexusObjectFieldWire0.size}:" + __nexusObjectFieldWire0
let __nexusObjectFieldWire1 = "${__nexusObjectValue.reserved}"
__nexusObjectWire = __nexusObjectWire + "${__nexusObjectFieldWire1.size}:" + __nexusObjectFieldWire1
return __nexusObjectWire
}
@TestCase
func case0() {
let __nexusSeqBefore0: QuotaState = __nexusObjectCtor0(10, 0)
let __nexusSeqAfter0 = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case0|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case0|1|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case0|1|COMPLETE")
}
@TestCase
func case1() {
let __nexusSeqBefore0Value: QuotaState = __nexusObjectCtor0(10, 0)
let __nexusSeqAfter0Value = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0Value, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case1|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0Value)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0Value)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0Value) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case1|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1: QuotaState = __nexusSeqAfter0Value
let __nexusSeqAfter1 = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore1, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case1|step1|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore1)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case1|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case1|2|COMPLETE")
}
@TestCase
func case2() {
let __nexusSeqBefore0ValueValue: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0ValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0ValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case2|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0ValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case2|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1Value: QuotaState = __nexusSeqAfter0ValueValue
let __nexusSeqAfter1Value = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore1Value, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case2|step1|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore1Value)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1Value)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1Value) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case2|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case2|2|COMPLETE")
}
@TestCase
func case3() {
let __nexusSeqBefore0ValueValueValue: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0ValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0ValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case3|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0ValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case3|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValue: QuotaState = __nexusSeqAfter0ValueValueValue
let __nexusSeqAfter1ValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore1ValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case3|step1|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore1ValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValue) != "o:QuotaState:2:1:02:20") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case3|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case3|2|COMPLETE")
}
@TestCase
func case4() {
let __nexusSeqBefore0ValueValueValueValue: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0ValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case4|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case4|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValue
let __nexusSeqAfter1ValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore1ValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case4|step1|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore1ValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case4|2|MODEL_MISMATCH")
return
}
let __nexusSeqBefore2: QuotaState = __nexusSeqAfter1ValueValueValue
let __nexusSeqAfter2 = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore2, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case4|step2|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore2)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter2)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter2) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case4|3|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case4|3|COMPLETE")
}
@TestCase
func case5() {
let __nexusSeqBefore0ValueValueValueValueValue: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0ValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case5|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case5|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case5|step1|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValue) != "o:QuotaState:2:1:02:20") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case5|2|MODEL_MISMATCH")
return
}
let __nexusSeqBefore2Value: QuotaState = __nexusSeqAfter1ValueValueValueValue
let __nexusSeqAfter2Value = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore2Value, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case5|step2|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore2Value)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter2Value)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter2Value) != "o:QuotaState:2:1:02:20") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case5|3|MODEL_MISMATCH")
return
}
let __nexusSeqBefore3: QuotaState = __nexusSeqAfter2Value
let __nexusSeqAfter3 = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore3, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case5|step3|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore3)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter3)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter3) != "o:QuotaState:2:1:02:20") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case5|4|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case5|4|COMPLETE")
}
@TestCase
func case6() {
let __nexusSeqBefore0ValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0ValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case6|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case6|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case6|step1|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case6|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case6|2|COMPLETE")
}
@TestCase
func case7() {
let __nexusSeqBefore0ValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case7|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case7|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case7|step1|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case7|2|MODEL_MISMATCH")
return
}
let __nexusSeqBefore2ValueValue: QuotaState = __nexusSeqAfter1ValueValueValueValueValueValue
let __nexusSeqAfter2ValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore2ValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case7|step2|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore2ValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter2ValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter2ValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case7|3|MODEL_MISMATCH")
return
}
let __nexusSeqBefore3Value: QuotaState = __nexusSeqAfter2ValueValue
let __nexusSeqAfter3Value = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore3Value, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case7|step3|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore3Value)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter3Value)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter3Value) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case7|4|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case7|4|COMPLETE")
}
@TestCase
func case8() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case8|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case8|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case8|step1|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case8|2|MODEL_MISMATCH")
return
}
let __nexusSeqBefore2ValueValueValue: QuotaState = __nexusSeqAfter1ValueValueValueValueValueValueValue
let __nexusSeqAfter2ValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore2ValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case8|step2|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore2ValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter2ValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter2ValueValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case8|3|MODEL_MISMATCH")
return
}
let __nexusSeqBefore3ValueValue: QuotaState = __nexusSeqAfter2ValueValueValue
let __nexusSeqAfter3ValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore3ValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case8|step3|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore3ValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter3ValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter3ValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case8|4|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case8|4|COMPLETE")
}
@TestCase
func case9() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case9|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case9|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case9|step1|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case9|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case9|2|COMPLETE")
}
@TestCase
func case10() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case10|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case10|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case10|step1|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case10|2|MODEL_MISMATCH")
return
}
let __nexusSeqBefore2ValueValueValueValue: QuotaState = __nexusSeqAfter1ValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter2ValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore2ValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case10|step2|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore2ValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter2ValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter2ValueValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case10|3|MODEL_MISMATCH")
return
}
let __nexusSeqBefore3ValueValueValue: QuotaState = __nexusSeqAfter2ValueValueValueValue
let __nexusSeqAfter3ValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore3ValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case10|step3|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore3ValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter3ValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter3ValueValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case10|4|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case10|4|COMPLETE")
}
@TestCase
func case11() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(10, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case11|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case11|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case11|step1|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case11|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case11|2|COMPLETE")
}
@TestCase
func case12() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(10, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case12|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case12|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case12|step1|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case12|2|MODEL_MISMATCH")
return
}
let __nexusSeqBefore2ValueValueValueValueValue: QuotaState = __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter2ValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore2ValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case12|step2|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore2ValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter2ValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter2ValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case12|3|MODEL_MISMATCH")
return
}
let __nexusSeqBefore3ValueValueValueValue: QuotaState = __nexusSeqAfter2ValueValueValueValueValue
let __nexusSeqAfter3ValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore3ValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case12|step3|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore3ValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter3ValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter3ValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case12|4|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case12|4|COMPLETE")
}
@TestCase
func case13() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(10, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case13|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case13|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case13|step1|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case13|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case13|2|COMPLETE")
}
@TestCase
func case14() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(10, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case14|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case14|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case14|step1|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case14|2|MODEL_MISMATCH")
return
}
let __nexusSeqBefore2ValueValueValueValueValueValue: QuotaState = __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter2ValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore2ValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case14|step2|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore2ValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter2ValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter2ValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case14|3|MODEL_MISMATCH")
return
}
let __nexusSeqBefore3ValueValueValueValueValue: QuotaState = __nexusSeqAfter2ValueValueValueValueValueValue
let __nexusSeqAfter3ValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore3ValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case14|step3|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore3ValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter3ValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter3ValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case14|4|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case14|4|COMPLETE")
}
@TestCase
func case15() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(10, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case15|step0|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case15|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_V4|2c8c3115d95a9761|case15|step1|QuotaState|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode2c8c3115d95a9761(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case15|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint2c8c3115d95a9761("NEXUS_SEQUENCE_END_V4|2c8c3115d95a9761|case15|2|COMPLETE")
}
}
