package bench
import std.core.println as __nexusSeqPrint74befd571eee185d
import std.unittest.*
import std.unittest.testmacro.*
private let __nexusV4Bound74befd571eee185d: (QuotaState, String) -> QuotaState = applyQuota
private func __nexusObjectCtor0(__nexusCtorField0: Int64, __nexusCtorField1: Int64): QuotaState { return QuotaState(__nexusCtorField0, __nexusCtorField1) }

@Test
class NexusSequencesV474befd571eee185d {
private func __nexusObjectEncode74befd571eee185d(__nexusObjectValue: QuotaState): String {
var __nexusObjectWire = "o:QuotaState:2:"
let __nexusObjectFieldWire0 = "${__nexusObjectValue.available}"
__nexusObjectWire = __nexusObjectWire + "${__nexusObjectFieldWire0.size}:" + __nexusObjectFieldWire0
let __nexusObjectFieldWire1 = "${__nexusObjectValue.reserved}"
__nexusObjectWire = __nexusObjectWire + "${__nexusObjectFieldWire1.size}:" + __nexusObjectFieldWire1
return __nexusObjectWire
}
@TestCase
func case0() {
let __nexusSeqBefore0: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0 = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case0|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case0|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1: QuotaState = __nexusSeqAfter0
let __nexusSeqAfter1 = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case0|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1) != "o:QuotaState:2:1:02:20") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case0|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case0|2|COMPLETE")
}
@TestCase
func case1() {
let __nexusSeqBefore0Value: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0Value = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0Value, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case1|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0Value)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0Value)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0Value) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case1|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1Value: QuotaState = __nexusSeqAfter0Value
let __nexusSeqAfter1Value = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1Value, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case1|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1Value)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1Value)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1Value) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case1|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case1|2|COMPLETE")
}
@TestCase
func case2() {
let __nexusSeqBefore0ValueValue: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0ValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0ValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case2|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0ValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case2|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValue: QuotaState = __nexusSeqAfter0ValueValue
let __nexusSeqAfter1ValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1ValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case2|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1ValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValue) != "o:QuotaState:2:1:02:20") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case2|2|MODEL_MISMATCH")
return
}
let __nexusSeqBefore2: QuotaState = __nexusSeqAfter1ValueValue
let __nexusSeqAfter2 = __nexusV4Bound74befd571eee185d(__nexusSeqBefore2, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case2|step2|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore2)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2) != "o:QuotaState:2:1:02:20") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case2|3|MODEL_MISMATCH")
return
}
let __nexusSeqBefore3: QuotaState = __nexusSeqAfter2
let __nexusSeqAfter3 = __nexusV4Bound74befd571eee185d(__nexusSeqBefore3, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case2|step3|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore3)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3) != "o:QuotaState:2:1:02:20") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case2|4|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case2|4|COMPLETE")
}
@TestCase
func case3() {
let __nexusSeqBefore0ValueValueValue: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0ValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0ValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case3|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0ValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case3|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValue
let __nexusSeqAfter1ValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1ValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case3|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1ValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case3|2|MODEL_MISMATCH")
return
}
let __nexusSeqBefore2Value: QuotaState = __nexusSeqAfter1ValueValueValue
let __nexusSeqAfter2Value = __nexusV4Bound74befd571eee185d(__nexusSeqBefore2Value, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case3|step2|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore2Value)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2Value)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2Value) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case3|3|MODEL_MISMATCH")
return
}
let __nexusSeqBefore3Value: QuotaState = __nexusSeqAfter2Value
let __nexusSeqAfter3Value = __nexusV4Bound74befd571eee185d(__nexusSeqBefore3Value, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case3|step3|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore3Value)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3Value)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3Value) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case3|4|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case3|4|COMPLETE")
}
@TestCase
func case4() {
let __nexusSeqBefore0ValueValueValueValue: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0ValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0ValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case4|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0ValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case4|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValue
let __nexusSeqAfter1ValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1ValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case4|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1ValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case4|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case4|2|COMPLETE")
}
@TestCase
func case5() {
let __nexusSeqBefore0ValueValueValueValueValue: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0ValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case5|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case5|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case5|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case5|2|MODEL_MISMATCH")
return
}
let __nexusSeqBefore2ValueValue: QuotaState = __nexusSeqAfter1ValueValueValueValueValue
let __nexusSeqAfter2ValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore2ValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case5|step2|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore2ValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2ValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2ValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case5|3|MODEL_MISMATCH")
return
}
let __nexusSeqBefore3ValueValue: QuotaState = __nexusSeqAfter2ValueValue
let __nexusSeqAfter3ValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore3ValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case5|step3|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore3ValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3ValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3ValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case5|4|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case5|4|COMPLETE")
}
@TestCase
func case6() {
let __nexusSeqBefore0ValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0ValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case6|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case6|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case6|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case6|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case6|2|COMPLETE")
}
@TestCase
func case7() {
let __nexusSeqBefore0ValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(20, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case7|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case7|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case7|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case7|2|MODEL_MISMATCH")
return
}
let __nexusSeqBefore2ValueValueValue: QuotaState = __nexusSeqAfter1ValueValueValueValueValueValueValue
let __nexusSeqAfter2ValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore2ValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case7|step2|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore2ValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2ValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2ValueValueValue) != "o:QuotaState:2:2:201:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case7|3|MODEL_MISMATCH")
return
}
let __nexusSeqBefore3ValueValueValue: QuotaState = __nexusSeqAfter2ValueValueValue
let __nexusSeqAfter3ValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore3ValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case7|step3|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore3ValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3ValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3ValueValueValue) != "o:QuotaState:2:2:102:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case7|4|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case7|4|COMPLETE")
}
@TestCase
func case8() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(10, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case8|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case8|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case8|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case8|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case8|2|COMPLETE")
}
@TestCase
func case9() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(10, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case9|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case9|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case9|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case9|2|MODEL_MISMATCH")
return
}
let __nexusSeqBefore2ValueValueValueValue: QuotaState = __nexusSeqAfter1ValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter2ValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore2ValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case9|step2|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore2ValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2ValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2ValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case9|3|MODEL_MISMATCH")
return
}
let __nexusSeqBefore3ValueValueValueValue: QuotaState = __nexusSeqAfter2ValueValueValueValue
let __nexusSeqAfter3ValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore3ValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case9|step3|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore3ValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3ValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3ValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case9|4|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case9|4|COMPLETE")
}
@TestCase
func case10() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(10, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case10|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case10|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case10|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case10|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case10|2|COMPLETE")
}
@TestCase
func case11() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(10, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case11|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case11|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case11|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case11|2|MODEL_MISMATCH")
return
}
let __nexusSeqBefore2ValueValueValueValueValue: QuotaState = __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter2ValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore2ValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case11|step2|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore2ValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2ValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2ValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case11|3|MODEL_MISMATCH")
return
}
let __nexusSeqBefore3ValueValueValueValueValue: QuotaState = __nexusSeqAfter2ValueValueValueValueValue
let __nexusSeqAfter3ValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore3ValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case11|step3|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore3ValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3ValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3ValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case11|4|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case11|4|COMPLETE")
}
@TestCase
func case12() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(10, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case12|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case12|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case12|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case12|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case12|2|COMPLETE")
}
@TestCase
func case13() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(10, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case13|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case13|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case13|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case13|2|MODEL_MISMATCH")
return
}
let __nexusSeqBefore2ValueValueValueValueValueValue: QuotaState = __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter2ValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore2ValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case13|step2|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore2ValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2ValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2ValueValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case13|3|MODEL_MISMATCH")
return
}
let __nexusSeqBefore3ValueValueValueValueValueValue: QuotaState = __nexusSeqAfter2ValueValueValueValueValueValue
let __nexusSeqAfter3ValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore3ValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case13|step3|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore3ValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3ValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3ValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case13|4|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case13|4|COMPLETE")
}
@TestCase
func case14() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(10, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case14|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case14|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case14|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case14|2|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case14|2|COMPLETE")
}
@TestCase
func case15() {
let __nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusObjectCtor0(10, 0)
let __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case15|step0|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore0ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case15|1|MODEL_MISMATCH")
return
}
let __nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter0ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case15|step1|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore1ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case15|2|MODEL_MISMATCH")
return
}
let __nexusSeqBefore2ValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter1ValueValueValueValueValueValueValueValueValueValueValueValueValueValueValue
let __nexusSeqAfter2ValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore2ValueValueValueValueValueValueValue, "\u{63}\u{61}\u{6e}\u{63}\u{65}\u{6c}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case15|step2|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore2ValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2ValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter2ValueValueValueValueValueValueValue) != "o:QuotaState:2:2:101:0") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case15|3|MODEL_MISMATCH")
return
}
let __nexusSeqBefore3ValueValueValueValueValueValueValue: QuotaState = __nexusSeqAfter2ValueValueValueValueValueValueValue
let __nexusSeqAfter3ValueValueValueValueValueValueValue = __nexusV4Bound74befd571eee185d(__nexusSeqBefore3ValueValueValueValueValueValueValue, "\u{72}\u{65}\u{73}\u{65}\u{72}\u{76}\u{65}")
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_V4|74befd571eee185d|case15|step3|QuotaState|${__nexusObjectEncode74befd571eee185d(__nexusSeqBefore3ValueValueValueValueValueValueValue)}|${__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3ValueValueValueValueValueValueValue)}")
if (__nexusObjectEncode74befd571eee185d(__nexusSeqAfter3ValueValueValueValueValueValueValue) != "o:QuotaState:2:1:02:10") {
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case15|4|MODEL_MISMATCH")
return
}
__nexusSeqPrint74befd571eee185d("NEXUS_SEQUENCE_END_V4|74befd571eee185d|case15|4|COMPLETE")
}
}
