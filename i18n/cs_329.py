# 1.0.329: the database agent's databases and accounts are each one cluster's.
S329 = {}
P329 = {
    "the {0} {1} on this server is {2}'s, of another authority (another cluster) - not given to {3}; choose another name, or take {4} away here first (otp_db_agent.py --forget {5})":
        '{0} {1} na tomto serveru patří uzlu {2} jiné autority (jiného clusteru) – {3} ho nedostane; zvolte jiné jméno, nebo tu nejdřív odeberte {4} (otp_db_agent.py --forget {5})',
    'the account {0} is there and owns other databases ({1}) - not taken over; choose another name':
        'účet {0} už existuje a vlastní jiné databáze ({1}) – nepřevezme se; zvolte jiné jméno',
    'the account {0} is there with rights beyond the database {1} ({2}) - not taken over; choose another name':
        'účet {0} už existuje s právy mimo databázi {1} ({2}) – nepřevezme se; zvolte jiné jméno',
    'the database {0} is there and other accounts have rights on it ({1}) - not taken over; choose another name':
        'databáze {0} už existuje a mají na ni práva jiné účty ({1}) – nepřevezme se; zvolte jiné jméno',
}
