import os
import sys
import numpy as np
import pandas as pd

# Column headers in the spreadsheet
ROUND = "Round"  # Round number
TYPE = "Type"  # Toss-up or Bonus
CATEGORY = "Category"  # Biology, Chemistry, Physics, Earth and Space, Math, Energy
FORMAT = "Format"  # Multiple Choice, Short Answer
QUESTION = "Question"  # Body of question
ANSWER_CHOICE_LETTERS = ["W", "X", "Y", "Z"]  # Answer choices for MC
ANSWER = "Answer"
ACCEPT = "Accept"  # Acceptable alternate answers
DO_NOT_ACCEPT = "Do Not Accept"  #

# Internal information
SUBCAT = "Subcategory"
WRITER = "Writer"
SOURCE = "Source"
DATE = "Date"
DIVISION = "Division (Approx)"
DIFFICULTY = "Difficulty"
QUALITY = "Quality"

# Legal options for types
TOSSUP, BONUS = "Toss-up", "Bonus"
CATEGORIES = ["Math", "Biology", "Chemistry", "Physics", "Earth and Space", "Energy"]
MULTIPLE_CHOICE, SHORT_ANSWER = "Multiple Choice", "Short Answer"


class FormatError(Exception):
    pass


class FormatWarning(Exception):
    pass


def is_nan(val):
    return val == "nan" if type(val) == str else np.isnan(val)


def check_type(row):
    if row[TYPE] not in [TOSSUP, BONUS]:
        raise FormatError("Question type invalid")


def check_format(row):
    if row[FORMAT] not in [MULTIPLE_CHOICE, SHORT_ANSWER]:
        raise FormatError("Question format invalid")
    if row[FORMAT] == MULTIPLE_CHOICE and any(
        is_nan(row[c]) for c in ANSWER_CHOICE_LETTERS
    ):  # If any answer choice is missing
        raise FormatError("Multiple choice question has missing answer choices")
    if row[FORMAT] == SHORT_ANSWER and not all(
        is_nan(row[c]) for c in ANSWER_CHOICE_LETTERS
    ):  # Not all cells empty
        raise FormatError("Short answer question has extraneous answer choices")


def check_category(row):
    if row[CATEGORY] not in CATEGORIES:
        raise FormatError("Question category invalid")


def check_question_single_line(row):
    if "\n" in row[QUESTION]:
        raise FormatError("Question spans multiple lines")


def check_mc_wording(row):
    if (
        row[FORMAT] == MULTIPLE_CHOICE
        and "which of the following" not in row[QUESTION].lower()
    ):
        raise FormatWarning(
            "Multiple choice question does not contain the phrase 'which of the following'"
        )


def check_question_negations(row):
    bad_negations = ["false", "cannot"]
    for w in bad_negations:
        if w in row[QUESTION].lower():
            raise FormatWarning(f"Question wording contains the word {w}")


def check_capital_negations(row):
    if "not" in row[QUESTION].lower() and "NOT" not in row[QUESTION]:
        raise FormatWarning("Question does not capitalize the word 'not'")


def satisfies_basic_latex(text):
    """
    Only checks for matching curly braces and an even number of dollar signs.
    """
    if type(text) != str:
        return True
    return text.count("{") == text.count("}") and text.count("$") % 2 == 0


def check_basic_latex(row):
    if not satisfies_basic_latex(row[QUESTION]):
        raise FormatWarning("Question might contain improperly formatted LaTeX")
    if row[FORMAT] == MULTIPLE_CHOICE and not all(
        satisfies_basic_latex(row[c]) for c in ANSWER_CHOICE_LETTERS
    ):
        raise FormatWarning("Answer choices might contain improperly formatted LaTeX")


checks_to_run = {
    check_type,
    check_format,
    check_category,
    check_question_single_line,
    check_mc_wording,
    check_question_negations,
    check_capital_negations,
    check_basic_latex,
}


def make_error_file(sheet, f):
    for row in sheet.itertuples():
        ix = row.Index
        row = row._asdict()
        for check in checks_to_run:
            try:
                check(row)
            except (FormatError, FormatWarning) as e:
                error_or_warning = "Error" if type(e) == FormatError else "Warning"
                f.write(f"{error_or_warning} on row {ix+2}: {e}\n")


def get_full_path(filename):
    return os.path.join(sys.path[0], filename)


if __name__ == "__main__":
    sheet_name, out_file_name = "sheet", "sheet_errors"
    sheet = pd.read_csv(get_full_path(f"{sheet_name}.csv"))
    with open(get_full_path(f"{out_file_name}.txt"), "w") as f:
        make_error_file(sheet, f)
    """
    TODO: Add support for:
        using \read and not \readas
        fractions not inline with question
        writing the preceding letter in the answer choice cell "W)"
        not writing the preceding letter in the answer cell
        using pronunciation or reading guides in the answer cell
        answer cell doesn't match answer choices
        multiple-item question formatting
        wording for pseudo-mc and ranking
        multiple-item questions with 4+ options, warning
        researchers in the X group at MIT for energy questions
        identifying names
        picking out NOT questions to double-check them
        answer format specification not at the beginning
        binary option in 2 positions
        accept, do not accept in corresponding cells
        first word of answers/answer choices capitalized
        no period/comma at end of answer choice
        units lowercase
        chemical equation reading guide
        negative numbers not in math mode
        $, % in a question
    Change to per-row: for each row, run all the checks
    """
