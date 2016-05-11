
HIDDEN = ['nsfw']
def queryFromParams(params):
    q = {'filter': {'withoutTags': set(HIDDEN)}}
    qf = q['filter']
    for k, v in params:
        try:
            if k == 'limit': q.setdefault('paging', {})['limit'] = int(v)
            elif k == 'skip': q.setdefault('paging', {})['skip'] = int(v)
            elif k == 'tag':
                if v != '':
                    qf.setdefault('tags', set()).append(v)
            elif k == 'withoutTag':
                if v != '':
                    qf.setdefault('withoutTags', set()).add(v)
            elif (k, v) == ('hidden', 'none'):
                # this is now order-dependent with a withoutTags=nsfw param
                for h in HIDDEN:
                    qf['withoutTags'].discard(h)
            elif k == 'onlyTagged':
                qf.setdefault('onlyTagged', []).append(v)
            elif k == 'type' and v in ['image', 'video']:
                qf['type'] = v
            elif k == 'sort':
                if v.startswith('random '):
                    _, seed = v.split(' ')
                    q.setdefault('sort', []).append({'random': int(seed)})
                elif v == 'random':
                    q.setdefault('sort', []).append({'random': 0})
                elif v == '-time':
                    q.setdefault('sort', []).append({'time': 'desc'})
                elif v == 'time':
                    q.setdefault('sort', []).append({'time': 'asc'})
                else:
                    raise ValueError
            elif k == 'time':
                # incomplete
                qf['timeRange'] = v.split(',')
            elif k == 'attrs':
                raise NotImplementedError
            elif k == 'after':
                raise NotImplementedError
            else:
                raise ValueError
        except ValueError:
            raise ValueError("unknown param %s=%s" % (k, v))

    q['filter']['withoutTags'] = sorted(q['filter']['withoutTags'])
    if q['filter'] == {'withoutTags': []}:
        del q['filter']
    return q
