import re, sys

def extract_dragon_read_rules(filepath, sub_name):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    target_id = 'com.dragon.read'
    if target_id not in content:
        print(f'  [{sub_name}] 未找到 {target_id}')
        return

    idx = content.find(target_id)
    print(f'  [{sub_name}] 找到! 位置: {idx}')

    start = content.rfind('{', 0, idx)
    if start == -1:
        print(f'  [{sub_name}] 无法定位应用起始位置')
        return

    brace_count = 0
    end = start
    for i in range(start, len(content)):
        if content[i] == '{':
            brace_count += 1
        elif content[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break

    app_block = content[start:end]

    group_pattern = re.compile(r"name\s*:\s*'([^']*)'")
    key_pattern = re.compile(r"key\s*:\s*(\d+)")
    enable_pattern = re.compile(r"enable\s*:\s*(true|false)")
    desc_pattern = re.compile(r"desc\s*:\s*'([^']*)'")

    groups = re.split(r'(?=key\s*:\s*\d+,?\s*name\s*:\s*\')', app_block)

    group_count = 0
    total_rules = 0
    in_groups = False

    groups_section_start = app_block.find('groups:[')
    if groups_section_start == -1:
        print(f'  [{sub_name}] 无法定位 groups 段')
        return

    groups_text = app_block[groups_section_start + 8:]

    g_matches = list(re.finditer(r"\{key\s*:\s*(\d+),\s*name\s*:\s*'([^']*)'", groups_text))

    print(f'  规则组数: {len(g_matches)}')

    for gm in g_matches:
        gkey = gm.group(1)
        gname = gm.group(2)
        g_start = gm.start()

        next_g = groups_text.find('{key:', g_start + 1)
        if next_g == -1:
            g_block = groups_text[g_start:]
        else:
            g_block = groups_text[g_start:next_g]

        enable_m = re.search(r'enable\s*:\s*(true|false)', g_block)
        enable_val = enable_m.group(1) if enable_m else '默认'

        desc_m = re.search(r"desc\s*:\s*'([^']*)'", g_block)
        desc_val = desc_m.group(1) if desc_m else ''

        rule_count = len(re.findall(r'\{key\s*:', g_block)) - 1
        if rule_count < 0:
            rule_count = 0

        rule_names = re.findall(r"name\s*:\s*'([^']*)'", g_block)
        rule_names = [n for n in rule_names if n != gname]

        group_count += 1
        total_rules += len(rule_names)
        print(f'    Group {group_count}: [key={gkey}] {gname} (enable={enable_val}, rules={len(rule_names)})')
        if desc_val:
            print(f'      desc: {desc_val}')
        for ri, rn in enumerate(rule_names):
            print(f'      Rule {ri+1}: {rn}')

    print(f'  规则总数: {total_rules}')

print('=== 番茄免费小说 (com.dragon.read) 规则对比 ===')
print()

extract_dragon_read_rules(r'd:\Project\GKD\temp_aoguai.json5', '奥怪')
print()
extract_dragon_read_rules(r'd:\Project\GKD\temp_mengnian.json5', '梦念逍遥')
print()
extract_dragon_read_rules(r'd:\Project\GKD\temp_ganlin.json5', '甘霖')
print()
extract_dragon_read_rules(r'd:\Project\GKD\temp_mrlc.json5', 'Mrlc')
