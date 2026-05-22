import pyjson5
import json
import copy
import hashlib
import sys
import os

SUB_FILES = [
    (r'd:\Project\GKD\temp_aoguai.json5', '奥怪'),
    (r'd:\Project\GKD\temp_mengnian.json5', '梦念逍遥'),
    (r'd:\Project\GKD\temp_ganlin.json5', '甘霖'),
    (r'd:\Project\GKD\temp_mrlc.json5', 'Mrlc'),
]

PRIORITY_ORDER = ['梦念逍遥', '奥怪', '甘霖', 'Mrlc']

def load_subscription(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return pyjson5.loads(f.read())

def normalize_str(v):
    if isinstance(v, list):
        return '|'.join(sorted(str(x) for x in v))
    return str(v)

def rule_fingerprint(rule):
    if not isinstance(rule, dict):
        return str(rule)
    parts = []
    for k in ['matches', 'anyMatches', 'excludeMatches']:
        v = rule.get(k)
        if v is not None:
            parts.append(k + ':' + normalize_str(v))
    for k in sorted(rule.keys()):
        if k in ('matches', 'anyMatches', 'excludeMatches', 'key', 'name', 'snapshotUrls', 'excludeSnapshotUrls'):
            continue
        parts.append(k + ':' + str(rule[k]))
    return hashlib.md5('|'.join(parts).encode()).hexdigest()

def rule_name_fingerprint(rule):
    if not isinstance(rule, dict):
        return None
    matches = rule.get('matches', '')
    any_matches = rule.get('anyMatches', '')
    return hashlib.md5(normalize_str(matches or any_matches).encode()).hexdigest()[:12]

def group_fingerprint(group):
    if not isinstance(group, dict):
        return str(group)
    parts = []
    name = group.get('name', '')
    parts.append('name:' + name)
    for k in sorted(group.keys()):
        if k in ('key', 'name', 'rules', 'snapshotUrls'):
            continue
        parts.append(k + ':' + str(group[k]))
    return hashlib.md5('|'.join(parts).encode()).hexdigest()

def group_name_key(group):
    return group.get('name', '').strip()

def merge_global_groups(all_subs):
    merged_groups = []
    seen_fps = set()

    for sub_name in PRIORITY_ORDER:
        for sub in all_subs:
            if sub['_source_name'] != sub_name:
                continue
            for g in sub.get('globalGroups', []):
                fp = group_fingerprint(g)
                if fp not in seen_fps:
                    seen_fps.add(fp)
                    merged_groups.append(copy.deepcopy(g))
    return merged_groups

def deduplicate_rules(rules):
    seen = set()
    result = []
    for r in rules:
        if not isinstance(r, dict):
            continue
        fp = rule_fingerprint(r)
        if fp not in seen:
            seen.add(fp)
            result.append(r)
    return result

def merge_similar_groups(groups):
    name_map = {}
    for g in groups:
        name = group_name_key(g)
        if name not in name_map:
            name_map[name] = []
        name_map[name].append(g)

    merged = []
    for name, same_name_groups in name_map.items():
        if len(same_name_groups) == 1:
            merged.append(same_name_groups[0])
            continue

        base = copy.deepcopy(same_name_groups[0])
        all_rules = list(base.get('rules', []))
        for other in same_name_groups[1:]:
            other_rules = other.get('rules', [])
            if isinstance(other_rules, list):
                all_rules.extend(other_rules)
            for k, v in other.items():
                if k in ('key', 'rules', 'name'):
                    continue
                if k not in base:
                    base[k] = v

        base['rules'] = deduplicate_rules(all_rules)
        merged.append(base)

    return merged

def merge_apps(all_subs):
    all_apps = {}
    for sub_name in PRIORITY_ORDER:
        for sub in all_subs:
            if sub['_source_name'] != sub_name:
                continue
            for app in sub.get('apps', []):
                app_id = app.get('id', '')
                if not app_id:
                    continue
                if app_id not in all_apps:
                    all_apps[app_id] = {
                        'id': app_id,
                        'name': app.get('name', ''),
                        'groups': [],
                        '_sources': set(),
                    }
                entry = all_apps[app_id]
                entry['_sources'].add(sub_name)
                if not entry.get('name') and app.get('name'):
                    entry['name'] = app['name']

                app_groups = app.get('groups', [])
                if not isinstance(app_groups, list):
                    continue
                for g in app_groups:
                    if not isinstance(g, dict):
                        continue
                    entry['groups'].append(copy.deepcopy(g))

    return all_apps

def optimize_app(app_entry):
    groups = app_entry.get('groups', [])

    merged_groups = merge_similar_groups(groups)

    for g in merged_groups:
        rules = g.get('rules', [])
        if isinstance(rules, list):
            g['rules'] = deduplicate_rules(rules)

    app_entry['groups'] = merged_groups
    return app_entry

def renumber_keys(groups):
    for i, g in enumerate(groups):
        if not isinstance(g, dict):
            continue
        g['key'] = i
        rules = g.get('rules', [])
        if isinstance(rules, list):
            for j, r in enumerate(rules):
                if isinstance(r, dict):
                    r['key'] = j

def clean_metadata(obj):
    if isinstance(obj, dict):
        new = {}
        for k, v in obj.items():
            if k.startswith('_'):
                continue
            new[k] = clean_metadata(v)
        return new
    elif isinstance(obj, list):
        return [clean_metadata(item) for item in obj]
    return obj

def merge_categories(all_subs):
    seen = set()
    merged = []
    for sub_name in PRIORITY_ORDER:
        for sub in all_subs:
            if sub['_source_name'] != sub_name:
                continue
            for cat in sub.get('categories', []):
                cat_key = cat.get('key')
                if cat_key not in seen:
                    seen.add(cat_key)
                    merged.append(cat)
    merged.sort(key=lambda x: x.get('key', 0))
    return merged

def to_json5(obj, indent=0):
    pad = '  ' * indent
    if isinstance(obj, bool):
        return 'true' if obj else 'false'
    if isinstance(obj, (int, float)):
        return str(obj)
    if isinstance(obj, str):
        escaped = obj.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
        return f"'{escaped}'"
    if isinstance(obj, list):
        if not obj:
            return '[]'
        items = []
        for item in obj:
            items.append(pad + '  ' + to_json5(item, indent + 1))
        return '[\n' + ',\n'.join(items) + '\n' + pad + ']'
    if isinstance(obj, dict):
        if not obj:
            return '{}'
        items = []
        for k, v in obj.items():
            val_str = to_json5(v, indent + 1)
            items.append(f"{pad}  {k}: {val_str}")
        return '{\n' + ',\n'.join(items) + '\n' + pad + '}'
    return str(obj)

def main():
    all_subs = []
    source_stats = {}
    for filepath, name in SUB_FILES:
        try:
            sub = load_subscription(filepath)
            sub['_source_name'] = name
            all_subs.append(sub)
            app_count = len(sub.get('apps', []))
            group_count = sum(len(a.get('groups', [])) for a in sub.get('apps', []) if isinstance(a.get('groups'), list))
            rule_count = sum(
                len(g.get('rules', []))
                for a in sub.get('apps', [])
                if isinstance(a.get('groups'), list)
                for g in a.get('groups', [])
                if isinstance(g, dict) and isinstance(g.get('rules'), list)
            )
            source_stats[name] = {'apps': app_count, 'groups': group_count, 'rules': rule_count}
            print(f'[{name}] 加载成功: {app_count} 应用, {group_count} 规则组, {rule_count} 规则')
        except Exception as e:
            print(f'[{name}] 加载失败: {e}')

    if not all_subs:
        print('没有成功加载任何订阅文件')
        sys.exit(1)

    print('\n--- 合并中 ---')

    merged_categories = merge_categories(all_subs)
    merged_global_groups = merge_global_groups(all_subs)
    merged_apps_dict = merge_apps(all_subs)

    total_before_groups = 0
    total_before_rules = 0
    for app in merged_apps_dict.values():
        for g in app.get('groups', []):
            total_before_groups += 1
            rules = g.get('rules', [])
            if isinstance(rules, list):
                total_before_rules += len(rules)

    for app_id, app in merged_apps_dict.items():
        optimize_app(app)

    renumber_keys(merged_global_groups)

    sorted_apps = sorted(merged_apps_dict.values(), key=lambda x: x.get('name', x.get('id', '')))
    for app in sorted_apps:
        renumber_keys(app['groups'])

    total_apps = len(sorted_apps)
    total_groups = sum(len(a['groups']) for a in sorted_apps)
    total_rules = sum(
        len(g.get('rules', []))
        for a in sorted_apps
        for g in a['groups']
        if isinstance(g.get('rules'), list)
    )

    multi_source_apps = {aid: a for aid, a in merged_apps_dict.items() if len(a.get('_sources', set())) > 1}

    print(f'\n=== 合并统计 ===')
    print(f'  应用数: {total_apps}')
    print(f'  规则组数: {total_before_groups} -> {total_groups} (去重 {total_before_groups - total_groups})')
    print(f'  规则总数: {total_before_rules} -> {total_rules} (去重 {total_before_rules - total_rules})')
    print(f'  全局规则组: {len(merged_global_groups)}')
    print(f'  多源覆盖应用: {len(multi_source_apps)}')

    result = {
        'id': 99999,
        'name': 'GKD合并优化订阅',
        'version': 1,
        'author': 'merged',
        'categories': merged_categories,
        'globalGroups': merged_global_groups,
        'apps': sorted_apps,
    }

    result = clean_metadata(result)

    output_path = r'd:\Project\GKD\merged_subscription.json5'

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(to_json5(result))

    file_size = os.path.getsize(output_path)
    print(f'\n输出文件: {output_path}')
    print(f'文件大小: {file_size / 1024 / 1024:.1f} MB')

    try:
        with open(output_path, 'r', encoding='utf-8') as f:
            verify = pyjson5.loads(f.read())
        v_apps = len(verify.get('apps', []))
        v_groups = sum(len(a.get('groups', [])) for a in verify.get('apps', []))
        v_rules = sum(
            len(g.get('rules', []))
            for a in verify.get('apps', [])
            for g in a.get('groups', [])
            if isinstance(g.get('rules'), list)
        )
        print(f'验证通过: {v_apps} 应用, {v_groups} 规则组, {v_rules} 规则')
    except Exception as e:
        print(f'验证失败: {e}')

if __name__ == '__main__':
    main()
