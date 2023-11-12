# Assumes the input on the command line is a spreadsheet (.csv), all categories have been concatenated, and all assignment can be done through round numbers (i.e. no paired questions)

import pandas as pd
import random
from enum import Enum
from itertools import zip_longest
import sys
import re

random.seed(0)

# Meta
YEAR = 2023

# Column names
ROUND_NUM = "Round"
TYPE = "Type"
FORMAT = "Format"
CATEGORY = "Category"
SUBCAT = "Subcategory"
MULT_ITEM = "Multiple-item"
BODY = "Question"
ANSWER = "Answer"
ACCEPT = "Accept"
DO_NOT_ACCEPT = "Do Not Accept"
W, X, Y, Z = "W", "X", "Y", "Z"
# Column values
TOSSUP = "Toss-up"
BONUS = "Bonus"
MC = "Multiple Choice"
SA = "Short Answer"


class Category(Enum):
    Math, Biology, Chemistry, Physics, EarthSpace, Energy = range(6)


category_mappings = {
    "Math": Category.Math,
    "Biology": Category.Biology,
    "Chemistry": Category.Chemistry,
    "Physics": Category.Physics,
    "Earth and Space": Category.EarthSpace,
    "Earth": Category.EarthSpace,
    "Space": Category.EarthSpace,
    "Energy": Category.Energy,
}

category_str_mappings = {
    Category.Math: "Math",
    Category.Biology: "Biology",
    Category.Chemistry: "Chemistry",
    Category.Physics: "Physics",
    Category.EarthSpace: "Earth and Space",
    Category.Energy: "Energy",
}

# Pattern, num_choices. In order of most restrictive to least restrictive.
mult_item_patterns = [
    ("(.*) 1\) (.*); 2\) (.*); 3\) (.*); 4\) (.*)", 4),
    ("(.*) 1\) (.*) 2\) (.*) 3\) (.*) 4\) (.*)", 4),
    ("(.*) 1\) (.*); 2\) (.*); 3\) (.*)", 3),
    ("(.*) 1\) (.*) 2\) (.*) 3\) (.*)", 3),
]


def make_item_block(items):
    begin = "\\begin{enumerate}[label={\\arabic*}), noitemsep]"
    block = [begin]
    for i in items:
        block.append("\\item")
        block.append(i)
    block.append("\\end{enumerate}")
    return " ".join(block)


def render_mult_item(body):
    for pattern, num_items in mult_item_patterns:
        match = re.search(pattern, body)
        if not match:
            continue
        item_block = make_item_block([match.group(i + 2) for i in range(num_items)])
        return "\n".join([match.group(1), item_block])

    return None


def render_body(body, answer_choices, is_mc, is_mult_item):
    print(body)
    if is_mult_item:
        body = render_mult_item(body)
        assert body is not None
    if is_mc:
        choices = f"\\wxyz{{{answer_choices[0]}}}{{{answer_choices[1]}}}{{{answer_choices[2]}}}{{{answer_choices[3]}}}"
        body = " ".join([body, choices])
    return body


class Question:
    def __init__(
        self,
        category,
        subcat,
        is_mult_item,
        body,
        ans,
        accept,
        do_not_accept,
        is_mc=False,
        answer_choices=None,
    ):  # By default, assumes short answer
        self.category = category
        self.subcat = subcat
        self.is_mult_item = is_mult_item
        self.body = body
        self.ans = ans
        self.accept = accept
        self.do_not_accept = do_not_accept
        self.is_mc = is_mc
        self.format = MC if is_mc else SA
        self.answer_choices = answer_choices

    # Triple curly braces because:
    # Double curly braces to get the curly brace characters, {}
    # Single curly braces inside to use f-string formatting
    def render(self, q_type, num):
        category = category_str_mappings[self.category]
        # Answer note: acceptable and unacceptable answers. TODO: clean this up?
        accept = f"ACCEPT: {self.accept}" if self.accept is not None else None
        do_not_accept = (
            f"DO NOT ACCEPT: {self.do_not_accept}"
            if self.do_not_accept is not None
            else None
        )
        ans_note = None
        if accept is not None and do_not_accept is not None:
            ans_note = ", ".join((accept, do_not_accept))
        elif accept is not None:
            ans_note = accept
        elif do_not_accept is not None:
            ans_note = do_not_accept
        if pd.isnull(self.ans):
            self.ans = "MISSING ANSWER, MUST FIX"  # TODO: fix hacky fix
        ans = (
            " ".join((self.ans, f"({ans_note})")) if ans_note is not None else self.ans
        )
        # Body of the question: stuff for if multiple choice or not
        body = render_body(
            self.body, self.answer_choices, self.is_mc, self.is_mult_item
        )
        return f"\\question{{{num}}}{{{q_type}}}{{{category}}}{{{self.format}}}{{{body}}}{{{ans}}}"


class QuestionPair:
    def __init__(self, tossup, bonus):
        assert tossup.category == bonus.category  # No mixed pairs
        if tossup.category == Category.Energy:
            # Energy pairs should be of the same category
            assert tossup.subcat is not None and tossup.subcat == bonus.subcat
        self.category = tossup.category
        self.tossup = tossup
        self.bonus = bonus

    def render(self, num):
        tossup = self.tossup.render("Toss up", num)  # fix constant string?
        bonus = self.bonus.render(BONUS, num)
        return "".join(["\\filbreak\n", tossup, "\n\n", bonus, "\n\n"])


NUM_ROUNDS = 14
ROUND_LENGTH = 23  # 4 of each main category, 3 Energy (Bio, Chem, Phys). TODO: fix if category targets are different!
CATEGORY_TARGETS = {
    Category.Math: 4,
    Category.Biology: 4,
    Category.Chemistry: 4,
    Category.Physics: 4,
    Category.EarthSpace: 4,
    Category.Energy: 3,
}


def get_category(row):
    return category_mappings[row[CATEGORY]]


def null_to_none(val):
    return val if not pd.isnull(val) else None


def booleanify(val):
    assert val in ("Yes", "No")
    return val == "Yes"


def get_question(row):
    accept = null_to_none(row[ACCEPT])
    do_not_accept = null_to_none(row[DO_NOT_ACCEPT])
    subcat = null_to_none(row[SUBCAT])
    is_mult_item = booleanify(row[MULT_ITEM])
    if row[FORMAT] == SA:
        return Question(
            category=get_category(row),
            subcat=subcat,
            is_mult_item=is_mult_item,
            body=row[BODY],
            ans=row[ANSWER],
            accept=accept,
            do_not_accept=do_not_accept,
        )
    return Question(
        category=get_category(row),
        subcat=subcat,
        is_mult_item=is_mult_item,
        body=row[BODY],
        ans=row[ANSWER],
        accept=accept,
        do_not_accept=do_not_accept,
        is_mc=True,
        answer_choices=(row[W], row[X], row[Y], row[Z]),
    )


# Take a DataFrame representing a set of questions, and place questions into buckets based on category.
# Returns a dictionary. Keys: Category, values: lists of Questions
def bucket_round(questions):
    buckets = {}
    for index, row in questions.iterrows():
        buckets.setdefault(get_category(row), []).append(get_question(row))
    # Energy questions should be sorted by subcategory; then when pairing buckets, subcategories are paired together
    if Category.Energy in buckets:
        buckets[Category.Energy].sort(key=lambda x: x.subcat)
    return buckets


# Precondition: same number of questions per category
def pair_buckets(tossup_buckets, bonus_buckets):
    return {
        cat: [
            QuestionPair(tu, bonus)
            for tu, bonus in zip(tossup_buckets[cat], bonus_buckets[cat])
        ]
        for cat in Category
        if cat in tossup_buckets
        # TODO: fix this, related to the category not having enough questions issue.
    }


# Checks the boundaries between question chunks to make sure there are no consecutive pairs with the same category
def has_repeat_cat(chunks):
    for i in range(len(chunks) - 1):
        if chunks[i][-1].category == chunks[i + 1][0].category:
            return True
    return False


# This function generates rounds in chunks of 6, 6, 6, and then 5. The first 3 have all 6 categories, and the last one is missing Energy.
def gen_round(question_df, round_num):  # Returns a list of QuestionPairs
    round_qs = question_df.loc[question_df[ROUND_NUM] == round_num]
    tossup_buckets = bucket_round(round_qs.loc[round_qs[TYPE] == TOSSUP])
    bonus_buckets = bucket_round(round_qs.loc[round_qs[TYPE] == BONUS])
    paired_qs = pair_buckets(tossup_buckets, bonus_buckets)

    chunks = []
    for chunk in zip_longest(*list(paired_qs.values())):
        good_chunk = [i for i in chunk if i is not None]
        random.shuffle(good_chunk)
        chunks.append(good_chunk)

    # Shuffle each chunk until there are no repeat categories across borders
    while has_repeat_cat(chunks):
        for c in chunks:
            random.shuffle(c)

    questions = []
    for chunk in chunks:
        questions.extend(chunk)
    return questions


# Returns a list of lists of QuestionPairs. Outer list is of length NUM_ROUNDS, and inner lists are of length ROUND_LENGTH.
def gen_all_rounds(question_df):
    return [gen_round(question_df, i + 1) for i in range(NUM_ROUNDS)]


# Takes in a list of QuestionPairs. Returns a string corresponding to the blocks
def gen_question_tex(question_pairs):
    return "\\hrulefill\n".join(
        [pair.render(i + 1) for i, pair in enumerate(question_pairs)]
    )


# Takes in a list of rounds, which are lists of QuestionPairs. Pass in the result from gen_all_rounds.
def gen_round_tex(rounds):
    return [gen_question_tex(r) for r in rounds]


if __name__ == "__main__":
    all_questions = pd.read_csv(sys.argv[1])
    # dtype={W: str, X: str, Y: str, Z: str, ANSWER: str}
    # all_questions = pd.read_csv("./all_questions.csv")
    with open("./round_template.tex", "r") as inf:
        template = inf.readlines()
    for i, tex_block in enumerate(gen_round_tex(gen_all_rounds(all_questions))):
        outname = f"./rounds-tex/Round {i+1}.tex"
        with open(outname, "w+") as outf:
            for line in template:
                newline = (
                    line.replace("INSERT_QUESTIONS_HERE", tex_block)
                    .replace("ROUND_NUMBER", str(i + 1))
                    .replace("YEAR", str(YEAR))
                )
                outf.write(newline)


# TODO: check category target matches in find_sheet_issues. check that short answer questions do NOT have WXYZ and MC questions have ALL wxyz.

# TODO: randomize order when the sheet is first taken in.

# TODO: also generate tiebreaks
