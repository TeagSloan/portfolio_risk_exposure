// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console} from "forge-std/Script.sol";
import {ExposureOracle} from "../src/ExposureOracle.sol";
import {MockExchange} from "../src/MockExchange.sol";
import {ThemeFundFactory} from "../src/ThemeFundFactory.sol";

/// Deploys the three long-lived contracts to Monad testnet. Run from contracts/ with the
/// deployer wallet stored in a Foundry keystore (never paste a private key):
///
///   forge script script/Deploy.s.sol --rpc-url monad --account <keystore-name> --broadcast
///
/// Then copy the printed ORACLE_ADDRESS and FACTORY_ADDRESS into .env.
/// The deployer becomes the owner of the oracle (can post results) and of the exchange
/// (can list stocks). Stocks are listed and results posted afterwards by chain/publish.py.
contract Deploy is Script {
    function run() external {
        vm.startBroadcast();
        ExposureOracle oracle = new ExposureOracle();
        MockExchange exchange = new MockExchange(oracle);
        ThemeFundFactory factory = new ThemeFundFactory(exchange);
        vm.stopBroadcast();

        console.log("ORACLE_ADDRESS=%s", address(oracle));
        console.log("EXCHANGE_ADDRESS=%s", address(exchange));
        console.log("USDC_ADDRESS=%s", address(exchange.usdc()));
        console.log("FACTORY_ADDRESS=%s", address(factory));
    }
}
