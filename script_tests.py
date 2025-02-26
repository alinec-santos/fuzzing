import re
import solcx
from web3 import Web3
import random
import subprocess
import shutil
import os
import json

# Função para extrair a versão do Solidity do pragma no contrato
def extract_solc_version(source_code):
    pragma_match = re.search(r"pragma solidity (\^?|>=?|<=?)?([0-9]+\.[0-9]+\.[0-9]+);", source_code)
    if pragma_match:
        return pragma_match.group(2)
    return None

# Função para compilar o contrato
def compile_smartcontract(contract_filename, source_code):
    solc_version = extract_solc_version(source_code)
    if not solc_version:
        print("Não foi possível detectar a versão do Solidity no contrato.")
        return None

    if solc_version not in solcx.get_installed_solc_versions():
        print(f"Instalando Solc versão {solc_version}...")
        solcx.install_solc(solc_version)

    solcx.set_solc_version(solc_version, True)

    # Ajuste da evmVersion com base na versão do Solidity
    if solc_version.startswith("0.4."):
        evm_version = "petersburg"  # ou "petersburg" para versões mais recentes do Solidity 0.4.x
    else:
        evm_version = "cancun"  # Mantém "cancun" para versões mais recentes do Solidity

    compiler_output = solcx.compile_standard({
        'language': 'Solidity',
        'sources': {contract_filename: {'content': source_code}},
        'settings': {
            "optimizer": {"enabled": True, "runs": 200},
            "evmVersion": evm_version,  
            "outputSelection": {
                contract_filename: {
                    "*": [
                        "abi",
                        "evm.deployedBytecode",
                        "evm.bytecode.object",
                        "evm.legacyAssembly",
                    ],
                }
            }
        }
    }, allow_paths='.')
    print("Smart contract compiled!")
    return compiler_output

# Função para conectar à blockchain
def connect_in_blockchain(url):
    w3 = Web3(Web3.HTTPProvider(url))
    if w3.is_connected():
        print("Blockchain connected successfully!")
        w3.eth.default_account = w3.eth.accounts[0]
        return w3
    print("Error during the connection with the blockchain!")
    return None

def get_constructor_args(abi):
    for item in abi:
        if item['type'] == 'constructor':
            return item['inputs']  # Retorna a lista de argumentos do construtor
    return None  # Retorna None se não houver construtor

def generate_constructor_args(abi):
    constructor_inputs = get_constructor_args(abi)
    if not constructor_inputs:
        return None  # Retorna None se não houver construtor

    args = {}
    for input_param in constructor_inputs:
        param_type = input_param['type']
        if param_type == 'uint256':
            value = random.randint(0, 2**256 - 1)
        elif param_type == 'address':
            value = Web3.to_checksum_address('0x' + ''.join(random.choices('0123456789abcdef', k=40)))
        elif param_type == 'string':
            value = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', k=random.randint(5, 15)))
        elif param_type == 'bool':
            value = random.choice([True, False])
        elif param_type.startswith('bytes'):
            size = int(param_type.replace('bytes', '')) if len(param_type) > 5 else random.randint(1, 32)
            value = '0x' + ''.join(random.choices('0123456789abcdef', k=size*2))
        else:
            value = None  # Tipos não suportados são ignorados
        if value is not None:
            args[input_param['name']] = value
    return args

# Função para fazer o deploy do contrato
def deploy_smartcontract(w3, abi, bytecode, constructor_args=None):
    smart_contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    if constructor_args:
        # Se o construtor exigir argumentos
        tx_hash = smart_contract.constructor(*constructor_args).transact()
    else:
        # Construtor sem argumentos
        tx_hash = smart_contract.constructor().transact()
    
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    contract_address = tx_receipt.contractAddress
    print(f"Contract Address: {contract_address}")
    return w3.eth.contract(address=contract_address, abi=abi)

# Função para gerar entradas aleatórias para qualquer tipo de parâmetro
def generate_random_inputs(abi):
    inputs = []
    for item in abi:
        if item['type'] == 'function':
            function_inputs = {}
            for input_param in item.get('inputs', []):
                param_type = input_param['type']
                if param_type == 'uint256':
                    value = random.randint(0, 2**256 - 1)
                elif param_type == 'address':
                    value = Web3.to_checksum_address('0x' + ''.join(random.choices('0123456789abcdef', k=40)))
                elif param_type == 'string':
                    value = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', k=random.randint(5, 15)))
                elif param_type == 'bool':
                    value = random.choice([True, False])
                elif param_type.startswith('bytes'):
                    size = int(param_type.replace('bytes', '')) if len(param_type) > 5 else random.randint(1, 32)
                    value = '0x' + ''.join(random.choices('0123456789abcdef', k=size*2))
                else:
                    value = None  # Tipos não suportados são ignorados
                if value is not None:
                    function_inputs[input_param['name']] = value
            inputs.append({
                'stateMutability': item["stateMutability"],
                'name': item['name'],
                'inputs': function_inputs
            })
    return inputs

def simulate_transaction(w3, contract, function_name, inputs=None, value=0):
    try:
        if function_name == 'withdraw':
            # Verifica o saldo antes de sacar
            caller_address = w3.eth.default_account
            balance = contract.functions.balances(caller_address).call()
            if balance <= 0:
                print(f"Saldo insuficiente para sacar. Saldo atual: {balance}")
                return None

        if inputs:
            sorted_inputs = [inputs[param] for param in inputs]
            txn = getattr(contract.functions, function_name)(*sorted_inputs).transact({'value': value})
        else:
            txn = getattr(contract.functions, function_name)().transact({'value': value})
        tx_receipt = w3.eth.wait_for_transaction_receipt(txn)
        print(f"Transaction '{function_name}' executed successfully: {tx_receipt.transactionHash.hex()}")
        return tx_receipt
    except Exception as e:
        print(f"Error during transaction '{function_name}' execution: {e}")
        return None

# Função para rastrear cobertura de código
def code_coverage(logs):
    covered_pcs = set()
    for log in logs:
        if "pc" in log:
            covered_pcs.add(log["pc"])
    return covered_pcs

# Função para atualizar o mapa de cobertura
def update_coverage(coverage_map, new_coverage):
    for pc in new_coverage:
        if pc not in coverage_map:
            coverage_map[pc] = 1
        else:
            coverage_map[pc] += 1
    return coverage_map

# Função para calcular a cobertura de código
def calculate_coverage(coverage_map, total_pcs):
    unique_pcs_covered = len(coverage_map.keys())
    coverage_percentage = (unique_pcs_covered / total_pcs) * 100
    print(f"Current Code Coverage: {coverage_percentage:.2f}%")
    return coverage_percentage

# Função para salvar chamadas de baixo nível
def save_lowlevelcalls(result, out_filename):
    result = dict(result)
    temp_logs = []
    for log in result["structLogs"]:
        temp_log = dict(log)
        temp_log["storage"] = dict(temp_log["storage"])
        temp_logs.append(temp_log)
    result["structLogs"] = temp_logs
    with open(out_filename, 'w') as fp:
        json.dump(result, fp)

# Adicione esta função ao código
def get_pcs_and_jumpis(bytecode):
    """
    Extrai os PCs (Program Counters) e as posições dos JUMPIs do bytecode.
    """
    pcs = [i for i in range(len(bytecode) // 2)]  # Cada byte no bytecode é representado por 2 caracteres hex
    jumpis = [i for i, opcode in enumerate(bytecode) if bytecode[i:i+2] == '57']  # '57' é o opcode de JUMPI
    return pcs, jumpis

# Variáveis globais para rastrear SLOADs e CALLs
sloads = {}
calls = set()

def detect_reentrancy(instruction, source_map):
    """
    Detecta reentrada com base em operações CALL e SSTORE.
    """
    global sloads, calls  # Usa as variáveis globais

    if instruction["op"] == "SLOAD":
        storage_index = instruction["stack"][-1]
        sloads[storage_index] = instruction["pc"]

    elif instruction["op"] == "CALL" and sloads:
        gas = int(instruction["stack"][-1], 16)
        value = int(instruction["stack"][-3], 16)
        if gas > 2300 and value > 0:
            calls.add(instruction["pc"])
            for pc in sloads.values():
                if pc < instruction["pc"]:
                    line_number, line_content = source_map.get_buggy_line(pc)
                    if line_number != -1:
                        print(f"Reentrância detectada na linha {line_number}: {line_content}")
                    return instruction["pc"]

    elif instruction["op"] == "SSTORE" and calls:
        storage_index = instruction["stack"][-1]
        if storage_index in sloads:
            for pc in calls:
                if pc < instruction["pc"]:
                    line_number, line_content = source_map.get_buggy_line(pc)
                    if line_number != -1:
                        print(f"Reentrância detectada na linha {line_number}: {line_content}")
                    return pc

    # Limpa sloads e calls no final da transação
    elif instruction["op"] in ["STOP", "RETURN", "REVERT", "ASSERTFAIL", "INVALID", "SUICIDE", "SELFDESTRUCT"]:
        sloads.clear()
        calls.clear()

    return None

def genetic_fuzzer(w3, abi, contract_instance, source_map, generations=3, population_size=1):
    population = [generate_random_inputs(abi) for _ in range(population_size)]
    coverage_map = {}
    total_pcs = len(source_map.instr_positions) if source_map.instr_positions else 1  # Evita divisão por zero

    for generation in range(generations):
        print(f"\nGeneration {generation}...")
        for inputs in population:
            for func in inputs:
                func_name = func['name']
                func_inputs = func['inputs'] if len(func['inputs']) > 0 else None
                func_state = func['stateMutability']
                value = 0
                
                if func_state == 'payable':
                    value = random.randint(1, 10**18)  # Valor aleatório para funções payable
                    print(f"Transaction `{func_name}` received random input value: {value}")
                
                # Se a função for 'withdraw', deposite Ether primeiro
                if func_name == 'withdraw':
                    deposit_value = random.randint(1, 10**18)  # Deposite um valor aleatório
                    print(f"Depositando {deposit_value} wei antes de sacar...")
                    deposit_receipt = simulate_transaction(w3, contract_instance, 'deposit', value=deposit_value)
                    if not deposit_receipt:
                        print("Erro ao depositar Ether. Ignorando saque.")
                        continue
                
                tx_receipt = simulate_transaction(w3, contract_instance, func_name, func_inputs, value)
                
                if tx_receipt:
                    result = w3.manager.request_blocking('debug_traceTransaction', [f"0x{tx_receipt.transactionHash.hex()}"])
                    logs = result["structLogs"] if "structLogs" in result else []
                    new_coverage = code_coverage(logs)
                    update_coverage(coverage_map, new_coverage)
                    
                    save_lowlevelcalls(result, f"gen{generation}_{func_name}.json")
                    
                    if not result.failed:
                        for instruction in result.structLogs:
                            pc = detect_reentrancy(instruction, source_map)
                            #if pc:
                                #print(f"Detected reentrancy in {func_name}: {pc}")
        
        if total_pcs > 0:  # Só calcula a cobertura se total_pcs for maior que zero
            calculate_coverage(coverage_map, total_pcs)
        else:
            print("Total PCs is zero. Cannot calculate coverage.")
# Classe para mapear o código-fonte
class Source:
    def __init__(self, filename):
        self.filename = filename
        self.content = self._load_content()
        self.line_break_positions = self._load_line_break_positions()

    def _load_content(self):
        with open(self.filename, 'r') as f:
            content = f.read()
        return content

    def _load_line_break_positions(self):
        return [i for i, letter in enumerate(self.content) if letter == '\n']

# Classe para mapear as posições do bytecode
class SourceMap:
    position_groups = {}
    sources = {}
    compiler_output = None

    def __init__(self, cname, compiler_output):
        self.cname = cname
        SourceMap.compiler_output = compiler_output
        SourceMap.position_groups = self._load_position_groups_standard_json()
        self.source = self._get_source()
        self.positions = self._get_positions()
        self.instr_positions = self._get_instr_positions()

    def _get_instr_positions(self):
        instr_positions = {}
        try:
            filename, contract_name = self.cname.split(":")
            bytecode = self.compiler_output['contracts'][filename][contract_name]["evm"]["deployedBytecode"]["object"]
            pcs, jumpis = get_pcs_and_jumpis(bytecode)
            for j, pc in enumerate(pcs):
                if j < len(self.positions) and self.positions[j]:
                    instr_positions[pc] = self.positions[j]
            return instr_positions
        except Exception as e:
            print(f"Erro ao mapear instruções: {e}")
            return instr_positions

    @classmethod
    def _load_position_groups_standard_json(cls):
        return cls.compiler_output["contracts"]

    def _get_positions(self):
        filename, contract_name = self.cname.split(":")
        asm = SourceMap.position_groups[filename][contract_name]['evm']['legacyAssembly']['.data']['0']
        positions = asm['.code']
        while True:
            try:
                positions.append(None)
                positions += asm['.data']['0']['.code']
                asm = asm['.data']['0']
            except KeyError:
                break
        return positions

    def _get_source(self):
        fname = self.get_filename()
        if fname not in SourceMap.sources:
            SourceMap.sources[fname] = Source(fname)
        return SourceMap.sources[fname]

    def get_filename(self):
        return self.cname.split(":")[0]

    def get_buggy_line(self, pc):
        try:
            pos = self.instr_positions[pc]
            line_number = sum(1 for i in self.source.line_break_positions if i < pos['begin']) + 1
            line_content = self.source.content[pos['begin']:pos['end']].strip()
            return line_number, line_content
        except KeyError:
            return -1, ""  # Retorna -1 e uma string vazia se não encontrar a posição

# Função principal
if __name__ == "__main__":
    contract_filename = "./reentrancy/ACCURAL_DEPOSIT.sol"
    contract_name = "ACCURAL_DEPOSIT"

    with open(contract_filename, 'r') as file:
        source_code = file.read()
    
    compiler_output = compile_smartcontract(contract_filename, source_code)
    if not compiler_output:
        exit()

    contract_interface = compiler_output['contracts'][contract_filename][contract_name]
    abi = contract_interface['abi']
    bytecode = contract_interface['evm']['bytecode']['object']
    
    blockhain_url = "http://127.0.0.1:8545"
    w3_conn = connect_in_blockchain(blockhain_url)
    if w3_conn is not None:
        # Gera argumentos para o construtor, se necessário
        constructor_args = generate_constructor_args(abi)
        if constructor_args:
            constructor_args = list(constructor_args.values())  # Converte o dicionário para uma lista
        else:
            constructor_args = None  # Sem construtor ou construtor sem argumentos

        contract_instance = deploy_smartcontract(w3_conn, abi, bytecode, constructor_args)
    
    source_map = SourceMap(f"{contract_filename}:{contract_name}", compiler_output)
    genetic_fuzzer(w3_conn, abi, contract_instance, source_map)
