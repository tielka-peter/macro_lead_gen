def state_unabbreviator(state):
    state = state.srtip().upper()
    
    match(state):
        case "VIC":
            unabbreviation = "victoria"
        case "NSW":
            unabbreviation = "new_south_wales"
        case "QLD":
            unabbreviation = "queensland"
        case "SA":
            unabbreviation = "south_australia"
        case "WA":
            unabbreviation = "western_australia"
        case "TAS":
            unabbreviation = "tasmania"
        case "NT":
            unabbreviation = "northern_territory"
        case "ACT":
            unabbreviation = "australian_capital_territory"
        
    return unabbreviation



while True:
    state = input("Enter state (e.g. NSW): ").strip().upper()
    print(state_unabbreviator(state))