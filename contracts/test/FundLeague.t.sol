// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {FundLeague, IPriceOracle} from "../src/FundLeague.sol";
import {ExposureOracle} from "../src/ExposureOracle.sol";

/// Tries to re-enter claim() while being paid.
contract GreedyPlayer {
    FundLeague public league;
    uint256 public roundId;
    uint256 public reentryAttempts;

    constructor(FundLeague l) {
        league = l;
    }

    function play(uint256 id, bytes32[] calldata tickers, uint16[] calldata weights) external payable {
        roundId = id;
        league.enter{value: msg.value}(id, "Greedy", tickers, weights);
    }

    function grab() external {
        league.claim(roundId);
    }

    receive() external payable {
        if (reentryAttempts == 0) {
            reentryAttempts++;
            try league.claim(roundId) {} catch {}
        }
    }
}

contract FundLeagueTest is Test {
    FundLeague league;
    ExposureOracle oracle;

    address alice = makeAddr("alice");
    address bob = makeAddr("bob");
    address carol = makeAddr("carol");
    address dave = makeAddr("dave");

    bytes32 constant DATA = keccak256("replay-prices-v2.json");
    uint256 constant WINDOWS = 400;
    uint256 constant DURATION = 60; // 20 replay days x 3 seconds
    uint256 constant STAKE = 1 ether;

    bytes32[] pool;

    function setUp() public {
        vm.warp(1_800_000_000);
        vm.roll(100);
        oracle = new ExposureOracle();
        league = new FundLeague(IPriceOracle(address(oracle)));
        string[8] memory names = ["NVDA", "AVGO", "NEM", "GOLD", "LLY", "MRK", "LMT", "XOM"];
        for (uint256 i = 0; i < names.length; i++) pool.push(bytes32(bytes(names[i])));
        _postAll(100e8);
        for (uint256 i = 0; i < 4; i++) vm.deal([alice, bob, carol, dave][i], 100 ether);
    }

    // ───────────── helpers ─────────────

    function _postAll(uint256 price) internal {
        uint256[] memory p = new uint256[](pool.length);
        for (uint256 i = 0; i < p.length; i++) p[i] = price;
        oracle.postPrices(pool, p);
    }

    function _post(string memory t, uint256 price) internal {
        oracle.postPrice(bytes32(bytes(t)), price);
    }

    function _open() internal returns (uint256 id) {
        id = league.openRound(pool, STAKE, block.timestamp + 60, DURATION, DATA, WINDOWS);
    }

    function _t3(string memory a, string memory b, string memory c) internal pure returns (bytes32[] memory t) {
        t = new bytes32[](3);
        (t[0], t[1], t[2]) = (bytes32(bytes(a)), bytes32(bytes(b)), bytes32(bytes(c)));
    }

    function _w3(uint16 a, uint16 b, uint16 c) internal pure returns (uint16[] memory w) {
        w = new uint16[](3);
        (w[0], w[1], w[2]) = (a, b, c);
    }

    function _enter(address who, uint256 id, string memory name, bytes32[] memory t, uint16[] memory w) internal {
        vm.prank(who);
        league.enter{value: STAKE}(id, name, t, w);
    }

    function _enterAiGoldHealth(uint256 id) internal {
        _enter(alice, id, "AI rocket", _t3("NVDA", "AVGO", "LLY"), _w3(5000, 3000, 2000));
        _enter(bob, id, "Gold bug", _t3("NEM", "GOLD", "MRK"), _w3(4000, 4000, 2000));
        _enter(carol, id, "Pharma", _t3("LLY", "MRK", "LMT"), _w3(3400, 3300, 3300));
    }

    /// Close entries, lock, wait for the target block, start (prices are $100 at start).
    function _lockAndStart(uint256 id) internal {
        vm.warp(block.timestamp + 61);
        _postAll(100e8); // the replayer resets the pool to $100 right before start
        league.lock(id);
        vm.roll(block.number + league.LOCK_DELAY() + 1);
        league.start(id);
    }

    function _settle(uint256 id) internal {
        vm.warp(block.timestamp + DURATION);
        league.settle(id);
    }

    function _claim(address who, uint256 id) internal returns (uint256 got) {
        uint256 before = who.balance;
        vm.prank(who);
        league.claim(id);
        got = who.balance - before;
    }

    function _score(uint256 id, uint256 i) internal view returns (int256 s) {
        (,,,, s) = league.getEntry(id, i);
    }

    // ───────────── entering ─────────────

    function test_valid_entry_is_stored_on_chain() public {
        uint256 id = _open();
        _enter(alice, id, "AI rocket", _t3("NVDA", "AVGO", "LLY"), _w3(5000, 3000, 2000));
        (address owner, string memory name, bytes32[] memory t, uint16[] memory w,) = league.getEntry(id, 0);
        assertEq(owner, alice);
        assertEq(name, "AI rocket");
        assertEq(t[0], bytes32("NVDA"));
        assertEq(t[2], bytes32("LLY"));
        assertEq(w[0], 5000);
        assertEq(league.entryOf(id, alice), 1);
        FundLeague.RoundInfo memory info = league.getRound(id);
        assertEq(info.pot, STAKE);
        assertEq(info.entryCount, 1);
    }

    function test_invalid_etfs_are_refused() public {
        uint256 id = _open();
        vm.startPrank(alice);
        vm.expectRevert("League: weights must add up to 100%");
        league.enter{value: STAKE}(id, "x", _t3("NVDA", "AVGO", "LLY"), _w3(5000, 3000, 1999));
        vm.expectRevert("League: each weight must be at least 5%");
        league.enter{value: STAKE}(id, "x", _t3("NVDA", "AVGO", "LLY"), _w3(9100, 499, 401));
        vm.expectRevert("League: stock is not in the pool");
        league.enter{value: STAKE}(id, "x", _t3("NVDA", "AVGO", "TSLA"), _w3(5000, 3000, 2000));
        vm.expectRevert("League: duplicate stock");
        league.enter{value: STAKE}(id, "x", _t3("NVDA", "AVGO", "NVDA"), _w3(5000, 3000, 2000));
        vm.expectRevert("League: one weight per stock");
        league.enter{value: STAKE}(id, "x", _t3("NVDA", "AVGO", "LLY"), new uint16[](2));
        vm.expectRevert("League: name must be 1 to 32 bytes");
        league.enter{value: STAKE}(id, "", _t3("NVDA", "AVGO", "LLY"), _w3(5000, 3000, 2000));
        vm.expectRevert("League: name must be 1 to 32 bytes");
        league.enter{value: STAKE}(id, "this name is far too long for a fund name", _t3("NVDA", "AVGO", "LLY"),
            _w3(5000, 3000, 2000));

        bytes32[] memory two = new bytes32[](2);
        (two[0], two[1]) = (bytes32("NVDA"), bytes32("AVGO"));
        uint16[] memory w2 = new uint16[](2);
        (w2[0], w2[1]) = (5000, 5000);
        vm.expectRevert("League: pick 3 to 8 stocks");
        league.enter{value: STAKE}(id, "x", two, w2);

        bytes32[] memory nine = new bytes32[](9);
        uint16[] memory w9 = new uint16[](9);
        for (uint256 i = 0; i < 8; i++) (nine[i], w9[i]) = (pool[i], 1000);
        (nine[8], w9[8]) = (bytes32("TSLA"), 2000);
        vm.expectRevert("League: pick 3 to 8 stocks");
        league.enter{value: STAKE}(id, "x", nine, w9);
        vm.stopPrank();
    }

    function test_eight_stocks_and_min_weights_are_allowed() public {
        uint256 id = _open();
        uint16[] memory w = new uint16[](8);
        for (uint256 i = 0; i < 7; i++) w[i] = 500; // 7 x 5% = 35%
        w[7] = 6500;
        vm.prank(alice);
        league.enter{value: STAKE}(id, "Eight", pool, w);
        assertEq(league.entryOf(id, alice), 1);
    }

    function test_wrong_stake_refused() public {
        uint256 id = _open();
        vm.startPrank(alice);
        vm.expectRevert("League: send exactly the entry stake");
        league.enter{value: 0.5 ether}(id, "x", _t3("NVDA", "AVGO", "LLY"), _w3(5000, 3000, 2000));
        vm.expectRevert("League: send exactly the entry stake");
        league.enter{value: 2 ether}(id, "x", _t3("NVDA", "AVGO", "LLY"), _w3(5000, 3000, 2000));
        vm.expectRevert("League: send exactly the entry stake");
        league.enter{value: 0}(id, "x", _t3("NVDA", "AVGO", "LLY"), _w3(5000, 3000, 2000));
        vm.stopPrank();
    }

    function test_second_entry_from_same_wallet_refused() public {
        uint256 id = _open();
        _enter(alice, id, "First", _t3("NVDA", "AVGO", "LLY"), _w3(5000, 3000, 2000));
        vm.prank(alice);
        vm.expectRevert("League: this wallet already entered");
        league.enter{value: STAKE}(id, "Second", _t3("NEM", "GOLD", "MRK"), _w3(5000, 3000, 2000));
    }

    function test_entry_after_deadline_refused() public {
        uint256 id = _open();
        vm.warp(block.timestamp + 60); // exactly at the deadline
        vm.prank(alice);
        vm.expectRevert("League: entries are closed");
        league.enter{value: STAKE}(id, "Late", _t3("NVDA", "AVGO", "LLY"), _w3(5000, 3000, 2000));
    }

    // ───────────── scoring and payouts ─────────────

    function test_return_math_for_a_multi_stock_etf_and_winner_takes_pot() public {
        uint256 id = _open();
        _enterAiGoldHealth(id);
        _lockAndStart(id);
        // NVDA +20%, AVGO +10%, LLY -5%, NEM +15%, GOLD +5%, MRK +2%, LMT +1%
        _post("NVDA", 120e8);
        _post("AVGO", 110e8);
        _post("LLY", 95e8);
        _post("NEM", 115e8);
        _post("GOLD", 105e8);
        _post("MRK", 102e8);
        _post("LMT", 101e8);
        _settle(id);
        // AI rocket: 50% x 20% + 30% x 10% + 20% x -5% = 10% + 3% - 1% = +12%
        assertEq(_score(id, 0), 0.12e18);
        // Gold bug: 40% x 15% + 40% x 5% + 20% x 2% = 6% + 2% + 0.4% = +8.4%
        assertEq(_score(id, 1), 0.084e18);
        // Pharma: 34% x -5% + 33% x 2% + 33% x 1% = -1.7% + 0.66% + 0.33% = -0.71%
        assertEq(_score(id, 2), -0.0071e18);
        assertEq(_claim(alice, id), 3 ether); // the whole pot
        vm.prank(bob);
        vm.expectRevert("League: nothing to claim");
        league.claim(id);
        assertEq(address(league).balance, 0);
    }

    function test_tie_splits_the_pot() public {
        uint256 id = _open();
        _enter(alice, id, "Twin A", _t3("NVDA", "AVGO", "LLY"), _w3(5000, 3000, 2000));
        _enter(bob, id, "Twin B", _t3("AVGO", "NVDA", "LLY"), _w3(3000, 5000, 2000)); // same ETF, other order
        _enter(carol, id, "Gold", _t3("NEM", "GOLD", "MRK"), _w3(4000, 4000, 2000));
        _lockAndStart(id);
        _post("NVDA", 130e8);
        _settle(id);
        assertEq(_score(id, 0), _score(id, 1));
        assertEq(league.getRound(id).winnerCount, 2);
        assertEq(_claim(alice, id), 1.5 ether);
        assertEq(_claim(bob, id), 1.5 ether);
        assertEq(league.claimable(id, carol), 0);
    }

    function test_three_way_tie_leaves_only_dust() public {
        uint256 id = _open();
        _enterAiGoldHealth(id);
        _lockAndStart(id); // nothing moves: all three returns are 0%
        _settle(id);
        assertEq(league.getRound(id).winnerCount, 3);
        assertEq(_claim(alice, id), 1 ether);
        assertEq(_claim(bob, id), 1 ether);
        assertEq(_claim(carol, id), 1 ether);
    }

    function test_single_entrant_is_refunded() public {
        uint256 id = _open();
        _enter(alice, id, "Lonely", _t3("NVDA", "AVGO", "LLY"), _w3(5000, 3000, 2000));
        vm.warp(block.timestamp + 61);
        league.lock(id);
        assertEq(uint256(league.getRound(id).phase), uint256(FundLeague.Phase.Cancelled));
        assertEq(_claim(alice, id), STAKE);
        vm.expectRevert("League: round is not locked");
        league.start(id);
    }

    function test_stalled_round_refunds_everyone() public {
        uint256 id = _open();
        _enterAiGoldHealth(id);
        vm.warp(block.timestamp + 61);
        vm.expectRevert("League: not stalled yet");
        league.cancelStalled(id);
        league.lock(id); // locked but never started
        vm.warp(block.timestamp + league.STALL_TIMEOUT());
        league.cancelStalled(id);
        assertEq(_claim(alice, id), STAKE);
        assertEq(_claim(bob, id), STAKE);
        assertEq(_claim(carol, id), STAKE);
        assertEq(address(league).balance, 0);
    }

    function test_double_claim_refused() public {
        uint256 id = _open();
        _enterAiGoldHealth(id);
        _lockAndStart(id);
        _post("NVDA", 150e8);
        _settle(id);
        _claim(alice, id);
        vm.prank(alice);
        vm.expectRevert("League: already claimed");
        league.claim(id);
    }

    function test_reentrancy_guard_blocks_a_second_payout() public {
        uint256 id = _open();
        GreedyPlayer g = new GreedyPlayer(league);
        g.play{value: STAKE}(id, _t3("NVDA", "AVGO", "LLY"), _w3(5000, 3000, 2000));
        _enter(bob, id, "Gold bug", _t3("NEM", "GOLD", "MRK"), _w3(4000, 4000, 2000));
        _lockAndStart(id);
        _post("NVDA", 150e8);
        _settle(id);
        g.grab();
        assertEq(address(g).balance, 2 ether); // paid once: the whole pot
        assertEq(g.reentryAttempts(), 1); // it tried, and the guard stopped it
        assertEq(address(league).balance, 0);
    }

    function test_settle_and_claim_timing() public {
        uint256 id = _open();
        _enterAiGoldHealth(id);
        vm.prank(alice);
        vm.expectRevert("League: round is not finished");
        league.claim(id);
        vm.expectRevert("League: round has not started");
        league.settle(id);
        _lockAndStart(id);
        vm.warp(block.timestamp + DURATION - 1);
        vm.expectRevert("League: race is not over yet");
        league.settle(id);
        vm.warp(block.timestamp + 1);
        league.settle(id);
    }

    function test_stale_price_blocks_start_and_settle() public {
        uint256 id = _open();
        _enterAiGoldHealth(id);
        vm.warp(block.timestamp + 61);
        league.lock(id);
        vm.roll(block.number + 4);
        vm.warp(block.timestamp + 2 days); // prices posted 2 days ago
        vm.expectRevert("League: a pool price is stale");
        league.start(id);
        _postAll(100e8);
        league.start(id);
        vm.warp(block.timestamp + 2 days); // replay stopped posting
        vm.expectRevert("League: a pool price is stale");
        league.settle(id);
    }

    function test_live_scores_follow_the_oracle() public {
        uint256 id = _open();
        _enterAiGoldHealth(id);
        _lockAndStart(id);
        _post("NVDA", 110e8); // day 1
        int256[] memory s = league.liveScores(id);
        assertEq(s[0], 0.05e18); // 50% x +10%
        assertEq(s[1], 0);
    }

    // ───────────── randomness: the window can't be known before lock ─────────────

    function test_window_cannot_be_known_before_lock() public {
        uint256 id = _open();
        _enterAiGoldHealth(id);
        vm.expectRevert("League: round is not locked");
        league.start(id);
        vm.warp(block.timestamp + 61);
        league.lock(id);
        uint256 target = league.getRound(id).targetBlock;
        assertEq(target, block.number + league.LOCK_DELAY());
        assertEq(blockhash(target), bytes32(0)); // the deciding block doesn't exist yet
        vm.expectRevert("League: target block not reached yet");
        league.start(id);
        vm.roll(target);
        vm.expectRevert("League: target block not reached yet");
        league.start(id);

        vm.roll(target + 1);
        uint256 snap = vm.snapshotState();
        vm.setBlockhash(target, keccak256("hash A"));
        league.start(id);
        uint256 windowA = league.getRound(id).windowIndex;
        vm.revertToState(snap);
        vm.setBlockhash(target, keccak256("hash B"));
        league.start(id);
        uint256 windowB = league.getRound(id).windowIndex;
        assertTrue(windowA != windowB);
        assertLt(windowA, WINDOWS);
        assertEq(windowA, uint256(keccak256(abi.encode(keccak256("hash A"), id, DATA))) % WINDOWS);
    }

    function test_start_falls_back_to_prevrandao_after_256_blocks() public {
        uint256 id = _open();
        _enterAiGoldHealth(id);
        vm.warp(block.timestamp + 61);
        league.lock(id);
        vm.roll(block.number + 1000);
        vm.prevrandao(bytes32(uint256(42)));
        _postAll(100e8);
        league.start(id);
        assertEq(league.getRound(id).windowIndex, uint256(keccak256(abi.encode(bytes32(uint256(42)), id, DATA))) % WINDOWS);
    }

    // ───────────── operator and inputs ─────────────

    function test_only_operator_opens_rounds_and_inputs_are_checked() public {
        vm.prank(alice);
        vm.expectRevert("League: only the operator");
        league.openRound(pool, STAKE, block.timestamp + 60, DURATION, DATA, WINDOWS);
        bytes32[] memory dup = new bytes32[](3);
        (dup[0], dup[1], dup[2]) = (bytes32("NVDA"), bytes32("AVGO"), bytes32("NVDA"));
        vm.expectRevert("League: duplicate ticker in pool");
        league.openRound(dup, STAKE, block.timestamp + 60, DURATION, DATA, WINDOWS);
        vm.expectRevert("League: entry stake must be > 0");
        league.openRound(pool, 0, block.timestamp + 60, DURATION, DATA, WINDOWS);
        vm.expectRevert("League: deadline must be in the future");
        league.openRound(pool, STAKE, block.timestamp, DURATION, DATA, WINDOWS);
        vm.expectRevert("League: missing replay data hash");
        league.openRound(pool, STAKE, block.timestamp + 60, DURATION, bytes32(0), WINDOWS);
        vm.expectRevert("League: need at least one replay window");
        league.openRound(pool, STAKE, block.timestamp + 60, DURATION, DATA, 0);
    }

    function test_data_hash_and_pool_are_recorded_before_entries() public {
        uint256 id = _open();
        FundLeague.RoundInfo memory info = league.getRound(id);
        assertEq(info.dataHash, DATA);
        assertEq(info.pool.length, pool.length);
        assertEq(uint256(info.phase), uint256(FundLeague.Phase.Open));
    }

    function test_events_are_emitted() public {
        vm.expectEmit(true, false, false, false);
        emit FundLeague.RoundOpened(1, pool, 0, 0, 0, bytes32(0), 0);
        uint256 id = _open();
        vm.expectEmit(true, true, true, true);
        emit FundLeague.Entered(id, alice, 0, "AI rocket", _t3("NVDA", "AVGO", "LLY"), _w3(5000, 3000, 2000));
        _enter(alice, id, "AI rocket", _t3("NVDA", "AVGO", "LLY"), _w3(5000, 3000, 2000));
        _enter(bob, id, "Gold bug", _t3("NEM", "GOLD", "MRK"), _w3(4000, 4000, 2000));
        vm.warp(block.timestamp + 61);
        vm.expectEmit(true, false, false, true);
        emit FundLeague.Locked(id, block.number + 3);
        league.lock(id);
        vm.roll(block.number + 4);
        league.start(id);
        _post("NVDA", 120e8);
        vm.warp(block.timestamp + DURATION);
        vm.expectEmit(true, false, false, true);
        emit FundLeague.Settled(id, 0.1e18, 1, 2 ether);
        league.settle(id);
        vm.expectEmit(true, true, false, true);
        emit FundLeague.Claimed(id, alice, 2 ether, false);
        vm.prank(alice);
        league.claim(id);
    }
}
