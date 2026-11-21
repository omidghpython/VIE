"""Conservative English diagnostics; not a semantic parser or proof of validity.

No example IDs, gold answers, retrieved text, or model calls are used. Unknown
wording is left for the semantic reviewer. Rules never rewrite a question/tree.
"""
import re


TARGET_WORDS = {
    'person': 'person actor actress author writer character director singer vocalist composer '
              'lover founder politician figure photographer cinematographer',
    'organization': 'company organization organisation university band firm corporation team',
    'place': 'place location country city town state province region river airport harbour harbor county',
    'work': 'manga anime film movie book novel play album song game drama',
    'date': 'year date birthday',
    'number': 'number length height distance population age latitude longitude',
    'other': 'nationality profession occupation currency focus product type',
}
WORD_TYPE = {word: kind for kind, words in TARGET_WORDS.items() for word in words.split()}


def answer_target(question):
    """Extract only explicit WH targets; abstain on indirect/possessive ambiguity."""
    text = ' '.join(question.casefold().split())
    if re.search(r'\b(?:truth value|boolean value|yes or no|true or false|whether)\b', text):
        return None
    if re.match(r'^(?:can|could|would|will) you\b|^what (?:is|was) (?:the )?(?:answer|result)\b', text):
        return None
    if re.match(r'^(?:is|are|was|were|do|does|did|has|have|had|can|could|will|would|should|must)\b', text):
        return None
    if re.match(r'^(?:who|whom)\b', text):
        # Publishers/developers/sponsors can be people OR organizations.
        if re.match(r'^who (?:published|developed|built|funded|sponsored|made|acquired|owns|produced)\b', text):
            return None
        return {'type': 'person', 'head': text.split()[0]}
    if re.match(r'^where\b', text):
        return {'type': 'place', 'head': 'where'}
    if re.match(r'^when\b', text):
        return {'type': 'date', 'head': 'when'}
    # Exclude quoted titles from target extraction, not from model inputs.
    masked = re.sub(r'"[^"\n]*"', ' ', text)
    numeric = re.search(r'\bhow (?:many|much|long|old|far)\b', masked)
    wh = re.search(r'\b(?:what|which)\b', masked)
    if numeric and (not wh or numeric.start() < wh.start()):
        return {'type': 'number', 'head': numeric.group()}
    if not wh:
        return None
    tail = masked[wh.end():].strip()
    # "What is the name of the manga ...?" still requests a work, not a person.
    tail = re.sub(r'^(?:(?:is|was)\s+)?(?:the\s+)?name of (?:the |a |an )?', '', tail)
    tail = re.sub(r'^(?:is|was) (?:the |a |an )', '', tail)
    words = re.findall(r"[a-z]+(?:['’]s)?|[?.,:]", tail)
    stops = {'is', 'are', 'was', 'were', 'did', 'does', 'do', 'has', 'have', 'had',
             'of', 'in', 'for', 'by', 'that', 'who', 'whom', 'with', 'on', 'from', '?', '.', ',', ':'}
    phrase = []
    for word in words[:7]:
        if word in stops:
            break
        if word.endswith(("'s", '’s')):
            return None
        phrase.append(word)
    for word in phrase:
        if word in WORD_TYPE:
            return {'type': WORD_TYPE[word], 'head': word}
    return None


def incompatible_types(expected, actual):
    # "other" is deliberately unspecified. A year can be represented as a
    # number or a date; treating that alone as a semantic error would overreach.
    return (expected != actual and 'other' not in (expected, actual)
            and {expected, actual} != {'date', 'number'})


def geographic_precision_errors(question, plan):
    """Do not add mandatory coordinates to a qualitative geographic comparison."""
    text = question.casefold()
    comparison = re.search(r'\b(?:farther|further|more)\s+(?:to\s+the\s+)?(?:north|south|east|west)\b|'
                           r'\b(?:northernmost|southernmost|easternmost|westernmost)\b', text)
    if not comparison or re.search(r'\b(?:latitudes?|longitudes?|coordinates?|degrees?)\b', text):
        return []
    errors = []
    for node in plan['nodes']:
        target = answer_target(node['question'])
        if not node['dependencies'] and target and target['head'] in ('latitude', 'longitude'):
            errors.append(f"{node['id']}: requires a numerical {target['head']} absent from the original request. "
                          'Ask for the location/city/state and compare the named entities; retain any '
                          'coordinates if present in evidence, but do not require them.')
    return errors


def binding_errors(plan):
    """Catch explicit misuse of a value as a person, or a person as a band.

    Most relation semantics, new names and intersections still require review.
    Restrict automatic rejections to these unambiguous lexical constructions.
    """
    by_id = {node['id']: node for node in plan['nodes']}
    errors = []
    property_heads = {'nationality', 'profession', 'occupation', 'year', 'date', 'birthday',
                      'length', 'height', 'distance', 'population', 'age', 'latitude', 'longitude'}
    for node in plan['nodes']:
        for dep in node['dependencies']:
            child = by_id[dep]
            target = answer_target(child['question'])
            slot = re.escape('{{' + dep + '}}')
            text = node['question'].casefold()
            person_relation = re.search(r'\b(?:lover|spouse|wife|husband) of\s+' + slot, text)
            actor_relation = re.search(r'\b(?:did|does)\s+' + slot + r'\s+(?:appear|star|act)\b', text)
            is_property = bool(target and target['head'] in property_heads)
            description = bool(re.match(r'^what (?:is|was) .+ known for\s*\??$',
                                        ' '.join(child['question'].casefold().split())))
            if (person_relation and is_property) or (actor_relation and (is_property or description)):
                errors.append(f"{node['id']}: {dep} supplies a property/description, but this relation needs "
                              'its person. Identify the entity first and pass that entity, preserving the property binding.')
            band_relation = re.search(r'\b(?:lead singer|vocalist|lead) of\s+' + slot, text)
            if band_relation and target and target['type'] == 'person':
                errors.append(f"{node['id']}: asks for the lead of {dep}, which already asks for a person. "
                              'Keep the band-to-singer direction; pass the band, not its singer, into this relation.')
    return errors
