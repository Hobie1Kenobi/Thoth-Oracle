"""
Deploy ERC-20 tokens + SimpleSwap DEX on XRPL EVM Sidechain.
Creates a complete on-chain trading environment with liquidity pools.

Deploys:
1. TestUSDC (ERC-20, 6 decimals)
2. TestWBTC (ERC-20, 8 decimals)
3. SimpleSwap (constant-product AMM with XRP/USDC and XRP/WBTC pools)
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3
from eth_account import Account
from solcx import compile_source, set_solc_version

set_solc_version("0.8.20")

with open("config/crosschain_config.json") as f:
    cfg = json.load(f)

w3 = Web3(Web3.HTTPProvider(cfg["xrpl_evm"]["rpc"], request_kwargs={"timeout": 30}))
acct = Account.from_key(cfg["wallet"]["private_key"])
ADDR = acct.address
CHAIN_ID = cfg["xrpl_evm"]["chain_id"]

ERC20_SOURCE = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract TestToken {
    string public name;
    string public symbol;
    uint8 public decimals;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    constructor(string memory _name, string memory _symbol, uint8 _decimals, uint256 _initialSupply) {
        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        totalSupply = _initialSupply;
        balanceOf[msg.sender] = _initialSupply;
        emit Transfer(address(0), msg.sender, _initialSupply);
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        require(balanceOf[msg.sender] >= amount, "Insufficient balance");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        emit Transfer(msg.sender, to, amount);
        return true;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        require(balanceOf[from] >= amount, "Insufficient balance");
        require(allowance[from][msg.sender] >= amount, "Insufficient allowance");
        balanceOf[from] -= amount;
        allowance[from][msg.sender] -= amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
        return true;
    }
}
"""

SWAP_SOURCE = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function decimals() external view returns (uint8);
    function symbol() external view returns (string memory);
}

contract SimpleSwap {
    struct Pool {
        address token;
        uint256 tokenReserve;
        uint256 xrpReserve;
        uint256 totalLPShares;
        mapping(address => uint256) lpShares;
        bool exists;
    }

    mapping(address => Pool) public pools;
    address[] public poolTokens;
    address public owner;
    uint256 public feeNumerator = 3;
    uint256 public feeDenominator = 1000;

    event PoolCreated(address indexed token, uint256 tokenAmount, uint256 xrpAmount);
    event Swap(address indexed user, address indexed token, bool buyToken, uint256 amountIn, uint256 amountOut);
    event LiquidityAdded(address indexed provider, address indexed token, uint256 tokenAmount, uint256 xrpAmount);

    constructor() { owner = msg.sender; }

    function createPool(address token, uint256 tokenAmount) external payable {
        require(!pools[token].exists, "Pool exists");
        require(msg.value > 0 && tokenAmount > 0, "Zero amounts");

        IERC20(token).transferFrom(msg.sender, address(this), tokenAmount);

        Pool storage pool = pools[token];
        pool.token = token;
        pool.tokenReserve = tokenAmount;
        pool.xrpReserve = msg.value;
        pool.exists = true;
        pool.totalLPShares = msg.value;
        pool.lpShares[msg.sender] = msg.value;
        poolTokens.push(token);

        emit PoolCreated(token, tokenAmount, msg.value);
    }

    function swapXRPForToken(address token) external payable {
        Pool storage pool = pools[token];
        require(pool.exists, "No pool");
        require(msg.value > 0, "Zero XRP");

        uint256 fee = (msg.value * feeNumerator) / feeDenominator;
        uint256 xrpIn = msg.value - fee;
        uint256 tokenOut = (pool.tokenReserve * xrpIn) / (pool.xrpReserve + xrpIn);

        require(tokenOut > 0 && tokenOut <= pool.tokenReserve, "Bad swap");

        pool.xrpReserve += msg.value;
        pool.tokenReserve -= tokenOut;

        IERC20(token).transfer(msg.sender, tokenOut);
        emit Swap(msg.sender, token, true, msg.value, tokenOut);
    }

    function swapTokenForXRP(address token, uint256 tokenAmount) external {
        Pool storage pool = pools[token];
        require(pool.exists, "No pool");
        require(tokenAmount > 0, "Zero tokens");

        IERC20(token).transferFrom(msg.sender, address(this), tokenAmount);

        uint256 fee = (tokenAmount * feeNumerator) / feeDenominator;
        uint256 tokenIn = tokenAmount - fee;
        uint256 xrpOut = (pool.xrpReserve * tokenIn) / (pool.tokenReserve + tokenIn);

        require(xrpOut > 0 && xrpOut <= pool.xrpReserve, "Bad swap");

        pool.tokenReserve += tokenAmount;
        pool.xrpReserve -= xrpOut;

        payable(msg.sender).transfer(xrpOut);
        emit Swap(msg.sender, token, false, tokenAmount, xrpOut);
    }

    function getPrice(address token) external view returns (uint256 tokenPerXRP, uint256 xrpPerToken) {
        Pool storage pool = pools[token];
        require(pool.exists, "No pool");
        tokenPerXRP = (pool.tokenReserve * 1e18) / pool.xrpReserve;
        xrpPerToken = (pool.xrpReserve * 1e18) / pool.tokenReserve;
    }

    function getPoolInfo(address token) external view returns (
        uint256 tokenReserve, uint256 xrpReserve, bool exists
    ) {
        Pool storage pool = pools[token];
        return (pool.tokenReserve, pool.xrpReserve, pool.exists);
    }

    function getPoolCount() external view returns (uint256) { return poolTokens.length; }

    receive() external payable {}
}
"""


def compile_and_deploy(source, contract_name, constructor_args=None, value=0):
    compiled = compile_source(source, output_values=["abi", "bin"])
    cid = f"<stdin>:{contract_name}"
    abi = compiled[cid]["abi"]
    bytecode = compiled[cid]["bin"]

    contract = w3.eth.contract(abi=abi, bytecode=bytecode)

    nonce = w3.eth.get_transaction_count(ADDR)
    gas_price = w3.eth.gas_price

    build_args = {
        "from": ADDR, "nonce": nonce, "gas": 3000000,
        "maxFeePerGas": gas_price * 2, "maxPriorityFeePerGas": gas_price,
        "chainId": CHAIN_ID, "value": value
    }

    if constructor_args:
        tx = contract.constructor(*constructor_args).build_transaction(build_args)
    else:
        tx = contract.constructor().build_transaction(build_args)

    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

    return receipt["contractAddress"], abi, receipt


def send_tx(tx_data):
    nonce = w3.eth.get_transaction_count(ADDR)
    tx_data["nonce"] = nonce
    tx_data["from"] = ADDR
    tx_data["chainId"] = CHAIN_ID
    tx_data.pop("gasPrice", None)
    tx_data.pop("maxFeePerGas", None)
    tx_data.pop("maxPriorityFeePerGas", None)
    gas_price = w3.eth.gas_price
    tx_data["maxFeePerGas"] = gas_price * 2
    tx_data["maxPriorityFeePerGas"] = gas_price
    signed = acct.sign_transaction(tx_data)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)


def main():
    bal = w3.eth.get_balance(ADDR)
    print("=" * 60)
    print("DEPLOY DEX ON XRPL EVM SIDECHAIN")
    print("=" * 60)
    print(f"\nWallet: {ADDR}")
    print(f"Balance: {bal / 1e18:.6f} XRP")
    print(f"Chain: {w3.eth.chain_id}")

    # 1. Deploy TestUSDC
    print("\n📦 Deploying TestUSDC...")
    usdc_supply = 10_000_000 * 10**6
    usdc_addr, usdc_abi, usdc_receipt = compile_and_deploy(
        ERC20_SOURCE, "TestToken",
        constructor_args=["Test USDC", "tUSDC", 6, usdc_supply]
    )
    print(f"  ✅ tUSDC: {usdc_addr} (gas: {usdc_receipt['gasUsed']})")

    # 2. Deploy TestWBTC
    print("\n📦 Deploying TestWBTC...")
    wbtc_supply = 100 * 10**8
    wbtc_addr, wbtc_abi, wbtc_receipt = compile_and_deploy(
        ERC20_SOURCE, "TestToken",
        constructor_args=["Test WBTC", "tWBTC", 8, wbtc_supply]
    )
    print(f"  ✅ tWBTC: {wbtc_addr} (gas: {wbtc_receipt['gasUsed']})")

    # 3. Deploy SimpleSwap
    print("\n📦 Deploying SimpleSwap DEX...")
    swap_addr, swap_abi, swap_receipt = compile_and_deploy(SWAP_SOURCE, "SimpleSwap")
    print(f"  ✅ DEX: {swap_addr} (gas: {swap_receipt['gasUsed']})")

    # 4. Approve tokens for DEX
    print("\n🔓 Approving tokens for DEX...")
    usdc_contract = w3.eth.contract(address=usdc_addr, abi=usdc_abi)
    wbtc_contract = w3.eth.contract(address=wbtc_addr, abi=wbtc_abi)
    swap_contract = w3.eth.contract(address=swap_addr, abi=swap_abi)

    max_approve = 2**256 - 1
    r = send_tx(usdc_contract.functions.approve(swap_addr, max_approve).build_transaction({"gas": 100000}))
    print(f"  tUSDC approved: {'✅' if r['status'] == 1 else '❌'}")
    r = send_tx(wbtc_contract.functions.approve(swap_addr, max_approve).build_transaction({"gas": 100000}))
    print(f"  tWBTC approved: {'✅' if r['status'] == 1 else '❌'}")

    # 5. Create liquidity pools
    print("\n💧 Creating XRP/tUSDC pool (20 XRP + 10,000 USDC)...")
    usdc_liq = 10_000 * 10**6
    xrp_liq = w3.to_wei(20, "ether")
    r = send_tx(swap_contract.functions.createPool(usdc_addr, usdc_liq).build_transaction({
        "gas": 300000, "value": xrp_liq
    }))
    print(f"  XRP/tUSDC pool: {'✅' if r['status'] == 1 else '❌'} (gas: {r['gasUsed']})")

    print("\n💧 Creating XRP/tWBTC pool (20 XRP + 0.5 WBTC)...")
    wbtc_liq = int(0.5 * 10**8)
    r = send_tx(swap_contract.functions.createPool(wbtc_addr, wbtc_liq).build_transaction({
        "gas": 300000, "value": xrp_liq
    }))
    print(f"  XRP/tWBTC pool: {'✅' if r['status'] == 1 else '❌'} (gas: {r['gasUsed']})")

    # 6. Check pool prices
    print("\n📊 Pool prices:")
    try:
        usdc_price = swap_contract.functions.getPrice(usdc_addr).call()
        print(f"  XRP/tUSDC: {usdc_price[0] / 1e18:.2f} USDC per XRP, {usdc_price[1] / 1e18:.8f} XRP per USDC")
    except Exception as e:
        print(f"  XRP/tUSDC: {e}")

    try:
        wbtc_price = swap_contract.functions.getPrice(wbtc_addr).call()
        print(f"  XRP/tWBTC: {wbtc_price[0] / 1e18:.8f} WBTC per XRP, {wbtc_price[1] / 1e18:.2f} XRP per WBTC")
    except Exception as e:
        print(f"  XRP/tWBTC: {e}")

    # 7. Execute test swap
    print("\n🔄 Test swap: 1 XRP → tUSDC")
    usdc_before = usdc_contract.functions.balanceOf(ADDR).call()
    r = send_tx(swap_contract.functions.swapXRPForToken(usdc_addr).build_transaction({
        "gas": 200000, "value": w3.to_wei(1, "ether")
    }))
    usdc_after = usdc_contract.functions.balanceOf(ADDR).call()
    usdc_gained = (usdc_after - usdc_before) / 10**6
    print(f"  Status: {'✅' if r['status'] == 1 else '❌'}")
    print(f"  Received: {usdc_gained:.2f} tUSDC for 1 XRP")

    print("\n🔄 Test swap: 100 tUSDC → XRP")
    xrp_before = w3.eth.get_balance(ADDR)
    usdc_sell = 100 * 10**6
    r2 = send_tx(swap_contract.functions.swapTokenForXRP(usdc_addr, usdc_sell).build_transaction({
        "gas": 200000
    }))
    xrp_after = w3.eth.get_balance(ADDR)
    xrp_gained = (xrp_after - xrp_before) / 1e18
    print(f"  Status: {'✅' if r2['status'] == 1 else '❌'}")
    print(f"  Received: {xrp_gained:.6f} XRP for 100 tUSDC")

    # 8. Save deployment config
    deploy_config = {
        "tokens": {
            "tUSDC": {"address": usdc_addr, "decimals": 6, "symbol": "tUSDC"},
            "tWBTC": {"address": wbtc_addr, "decimals": 8, "symbol": "tWBTC"},
        },
        "dex": {"address": swap_addr, "name": "SimpleSwap"},
        "chain": {"id": CHAIN_ID, "rpc": cfg["xrpl_evm"]["rpc"]},
        "deployer": ADDR
    }
    with open("config/evm_dex_config.json", "w") as f:
        json.dump(deploy_config, f, indent=2)

    final_bal = w3.eth.get_balance(ADDR)
    print(f"\n📊 Final balance: {final_bal / 1e18:.6f} XRP")

    print(f"\n{'='*60}")
    print("DEPLOYMENT COMPLETE")
    print(f"{'='*60}")
    print(f"  tUSDC:     {usdc_addr}")
    print(f"  tWBTC:     {wbtc_addr}")
    print(f"  SimpleSwap: {swap_addr}")
    print(f"  Pools: XRP/tUSDC + XRP/tWBTC")
    print(f"  Test swap: 1 XRP → {usdc_gained:.2f} tUSDC ✅")
    print(f"  Explorer: {cfg['xrpl_evm']['explorer']}/address/{swap_addr}")


if __name__ == "__main__":
    main()
