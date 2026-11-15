# Fantasy Funds League: live demo guide

**Testnet MON only, no real money.** Anyone with a wallet builds their **own** mini-ETF from our stock pool,
stakes 1 MON and enters. After entries close, a future block's hash picks a random window of real past prices,
which is replayed on screen one day every 3 seconds. The entry with the best return takes the whole pot (ties
split it). With fewer than 2 entries, or if the round stalls, everyone gets their stake back.

## How it fits together

| Piece | What it does |
|---|---|
| `contracts/src/FundLeague.sol` | Entries (validated ETFs + stake), lock, random window, start/end prices, scoring, claims |
| `chain/league.py` | Operator: deploys the League's **own** oracle + FundLeague, picks the 60-stock pool, opens a round, runs lock → start → replay → settle |
| `chain/league_bets.py` | Backup: enters 3–4 sample ETFs from test wallets, and claims for them |
| `league/index.html` | The page: Build your ETF, entries list, countdown, live leaderboard, winner, Claim |
| `league/pool.json` | The 60 pool stocks with each stock's engine result per theme (powers "Build your ETF") |
| `league/presets.json` | The engine builder's suggestions for common Want/Avoid combos, restricted to the pool |
| `league/replay_prices.json` | Real past closes for the pool; its hash is fixed on-chain before anyone enters |
| `deployments/<network>.json` | Addresses. The League writes only its own `"league"` section |

The League never uses the main demo's contracts (it has its own oracle), so replaying old prices can't change
the dashboard or the "try adding XOM" demo.

**ETF rules** (checked by the contract and by the page): 3–8 stocks from the pool, no duplicates, each weight at
least 5%, weights adding up to exactly 100%, one entry per wallet per round, exactly the entry stake, and a name of
up to 32 characters.

## Commands

### Rehearsal on a local Anvil chain

```bash
# terminal 1: a local chain (--host 0.0.0.0 lets phones on the same Wi-Fi reach it)
~/.foundry/bin/anvil --host 0.0.0.0

# terminal 2, from the project folder
source .venv/bin/activate
(cd contracts && forge build)
python -m chain.league deploy --network anvil
python -m chain.league pool   --network anvil              # writes league/pool.json + league/presets.json
python -m chain.league open   --network anvil --entry-seconds 300 --stake 1

# terminal 3: serve the page from the project folder
python -m http.server 8000
#   laptop: http://localhost:8000/league/?network=anvil
#   phone on the same Wi-Fi: http://<laptop-ip>:8000/league/?network=anvil
#   (for phones on Anvil, set "rpc" in deployments/anvil.json to http://<laptop-ip>:8545)

# backup entries, if needed: 4 sample ETFs from 4 test wallets
python -m chain.league_bets enter --network anvil --count 4

# terminal 2 again: waits for the deadline, then lock -> start -> 20-day replay -> settle
python -m chain.league run --network anvil

# backup wallets claim (players press Claim on the page)
python -m chain.league_bets claim --network anvil
python -m chain.league status --network anvil
```

All in one go for a rehearsal: `python -m chain.league demo --network anvil --entry-seconds 60`.

### Live on Monad testnet

```bash
# once: the operator wallet in a Foundry keystore (asks for the key and a password; never paste it anywhere else)
cast wallet import deployer --interactive

python -m chain.league deploy --network monad-testnet      # -> deployments/monad-testnet.json "league"
python -m chain.league pool   --network monad-testnet
python -m chain.league open   --network monad-testnet --entry-seconds 300 --stake 1
python -m chain.league run    --network monad-testnet      # start right away and leave it running (see "Timing")
```

**Timing.** `run` must call `start` within 256 blocks of the target block, otherwise the contract falls back to
`prevrandao`. That's about 2 minutes on Monad. `run` does it automatically, so start it before the deadline and
leave it running.

## Hosting the page (GitHub Pages)

The page is static: it reads everything from the chain plus a few JSON files next to it, so GitHub Pages can
host it. These must be **committed and pushed** for the live round:

- `league/index.html`, `league/pool.json`, `league/presets.json`, `league/replay_prices.json`
- `deployments/monad-testnet.json` (with the `"league"` section written by `deploy`/`pool`/`open`)

Then enable Pages for the repo (Settings → Pages → deploy from the branch, root folder). The link to share is
`https://<owner>.github.io/<repo>/league/?network=monad-testnet`. Put it in the QR code on the big screen;
the page shows its own QR code too.

Re-push `deployments/monad-testnet.json` and `league/replay_prices.json` after each `open`, because a new round
writes a new replay file. The live leaderboard and the replay day come from the chain, so nothing needs pushing
during the race. Don't push `deployments/anvil.json`, `league/live.json` or `league/cost_report.json`; they're
local only.

## Testnet MON budget

Measured on Anvil (one setup and one round with 4 entries), priced at Monad testnet's 102 gwei. Monad charges
the gas **limit** a transaction asks for; every transaction asks for the estimate × 1.15.

| Who / step | Transactions | Gas limit | MON |
|---|---|---|---|
| Operator: deploy oracle + FundLeague (once) | 2 | 4.19 M | 0.43 |
| Operator: open (pool at $100 + openRound) | 2 | 6.76 M | 0.69 |
| Operator: lock, $100 reset, start | 3 | 3.07 M | 0.31 |
| Operator: 20-day replay (60 prices per day) | 20 | 17.59 M | 1.79 |
| Operator: settle (4 entries; ~+0.004 MON per extra entry) | 1 | 2.56 M | 0.26 |
| **Operator: one round** | 26 | 30.0 M | **3.06** |
| Player: one entry | 1 | 0.28 M | 0.028 + the 1 MON stake |
| Player: one claim | 1 | 0.09 M | 0.009 |

**Operator wallet: put in 20 MON.** Setup plus 3 rounds is about 9.6 MON. That covers a rehearsal, the live round
and a spare, with roughly 2× margin for gas-price spikes and bigger rounds.
**Each player: 5 MON** covers stakes and gas for 3 rounds with room to spare. With about 200 MON across the team,
that's 20 for the operator, 5 each for 3–4 players and a few for the backup wallets (`league_bets` tops each one
up with 1.05 MON). That leaves well over 100 MON in reserve.

## Checklist for each teammate (before the pitch)

1. **Install MetaMask** on your phone and create or import a wallet.
2. **Add Monad Testnet**: open the League page inside the MetaMask app's browser and tap **Add Monad Testnet**.
   Or add it by hand: name `Monad Testnet`, RPC `https://testnet-rpc.monad.xyz`, chain ID `10143`, symbol
   `MON`, explorer `https://testnet.monadexplorer.com`.
3. **Get testnet MON**: from the team pool (ask the operator) or https://faucet.monad.xyz. You need 5 MON.
4. **Open the page**: scan the QR code, or tap **Open in MetaMask app** if your phone opened it in a normal
   browser. Tap **Connect MetaMask** and approve.
5. **Rehearse once**: in the rehearsal round, build an ETF (pick Want/Avoid, adjust it, name it), tap
   **Enter (1 MON)** and check it appears in the entries list. Press **Claim** after the race.

## Who does what during the pitch

| Who | Job |
|---|---|
| **Operator** (laptop) | Runs `open` before the pitch and `run` straight after; shows the page full-screen on the projector |
| **Presenter** | Explains the game while entries are open; points at the QR code; narrates the race |
| **Teammates 1–3** (phones) | Build and enter their own ETFs live, ideally with different themes; press **Claim** after the winner banner |
| **Backup** (second laptop) | If phones fail, runs `python -m chain.league_bets enter --network monad-testnet --count 4` before the deadline, then `claim` after |

**Script, about 6 minutes:**
1. 0:00: the round is already open, and the QR code is on screen. "Build your own ETF: pick what you want and what to avoid."
2. 0:00–5:00: teammates build and enter; the entries list and pot grow on every phone.
3. 5:00: entries close. "A block that doesn't exist yet now picks which stretch of real history we replay."
4. 5:05–6:10: the race. One day every 3 seconds; the leaderboard reorders live.
5. 6:10: the winner banner. The winner taps **Claim** and the pot lands in their wallet.

## If something goes wrong

| Problem | Fix |
|---|---|
| A phone can't connect | Use the MetaMask app's built-in browser (not Safari/Chrome); tap **Add Monad Testnet** |
| "Entries are closed" | The deadline passed; this round's entries are over |
| Enter button stays grey | Check the list under the stocks: 3–8 stocks, each ≥ 5%, total 100%, no duplicates, a name |
| Nobody can enter | Run the backup entries from `chain.league_bets` before the deadline |
| Only one entry | No race: the round is cancelled at lock and the stake can be claimed back |
| `run` crashed before start | Run `python -m chain.league run --network <net>` again |
| `run` crashed mid-replay | Prices stop moving; once the race time has passed, `python -m chain.league run` can't restart it, so call `settle` with `cast send <FundLeague> "settle(uint256)" <round>` |
| A round never started | After 1 day anyone can call `cancelStalled`; everyone claims their stake back |
