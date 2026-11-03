package bench

public func applyQuota(state: QuotaState, action: String): QuotaState {
    if (action == "reserve") {
        if (state.available <= 10) { return state }
        return QuotaState(state.available - 10, state.reserved + 10)
    }
    if (action == "cancel") {
        if (state.reserved < 10) { return state }
        return QuotaState(state.available + 10, state.reserved)
    }
    return state
}

// local defect validation
