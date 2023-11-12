import pandas as pd
import numpy as np
import sys
import re
import os
import csv

pd.options.mode.chained_assignment = None

rand = lambda x: x + np.random.uniform(low=-1, high=1)

categories = ["Math", "Physics", "Chemistry", "Biology", "Earth and Space", "Energy"]

category_targets = [4, 4, 4, 4, 4, 3]

num_rounds = 13
num_tb = 10
round_robin = 0  # turn into 5 if desired

SA = "Short Answer"
MC = "Multiple Choice"

np.random.seed(1234)


def texify(text):
    if text.count("{") != text.count("}"):
        print(f"Warning: mismatched brackets: {text}")
    assert "\read{" not in text, f"use \\readas not \\read: {text}"
    # Subscripts and superscripts inside math mode
    if "$" not in text:
        text = re.sub(r"(\s)([^$\s]*[\^_][^$\s}]*?)([\s?.])", r"\1$\2$\3", text)
    # Use enumerate environments
    for i in range(7, 1, -1):
        t1 = "".join(str(j) + r"\)([\s\S]*)" for j in range(1, i + 1))
        t2 = (
            r"\\begin{enumerate}[label={\\arabic*}), noitemsep]"
            + "".join(r"\\item " + "\\" + str(j) for j in range(1, i + 1))
            + r"\\end{enumerate}"
        )
        text = re.sub(t1, t2, text)
    text = re.sub(
        r"W\)([\s\S]*)X\)([\s\S]*)Y\)([\s\S]*)Z\)([\s\S]*)",
        r"\\wxyz{\1}{\2}{\3}{\4}",
        text,
    )
    # Remove all trailing whitespace
    text = re.sub(r"\s+$", r"", text)
    text = re.sub(r"([^\\])%", r"\1\\%", text)
    return text


def get_data(f):  # pulls out everything from the .csv file
    qs = pd.read_csv(f, delimiter=",", quotechar='"')
    assert set(np.unique(qs["Category"])) == set(categories)
    # assert set(np.unique(qs['Type'])) == {SA, MC}
    # TODO reinstate above
    qs.insert(0, "round_number", 0)
    qs.insert(len(qs.columns), "pair_id", -1)
    # TODO process so that they all say "Toss up" or "Bonus" depending on first char
    qs.insert(
        len(qs.columns),
        "is_bonus",
        qs["Toss up/Bonus"].apply(lambda s: s.lower().strip() == "bonus"),
    )
    qs.insert(len(qs.columns), "new_diff", qs.Difficulty)
    qs.insert(len(qs.columns), "forced_pair", False)
    # qs.Question = qs.Question.apply(texify)
    # qs.Answer = qs.Answer.apply(texify)
    return [
        qs[qs["Category"] == c].reset_index(drop=True) for c in categories
    ]  # pandas data frame for each category


def assign(qs, rand=(lambda d: d)):  # rand: perturbation function
    # averages difficulty and quality ratings for pairs
    cat_id = categories.index(qs["Category"][0])
    per_round = category_targets[cat_id]
    target = per_round * num_rounds
    curr_id = 0
    for i in range(len(qs)):
        if qs["pair_id"][i] == -1:
            if np.count_nonzero(qs["Pairing"] == qs["Pairing"][i]) == 2:
                bool_arr = qs["Pairing"] == qs["Pairing"][i]
                for j in range(len(bool_arr)):
                    if bool_arr[j]:
                        qs.at[j, "pair_id"] = curr_id
                        qs.at[j, "forced_pair"] = True
                # print(qs['Pairing'] == qs['Pairing'][i])
                # qs.at[qs['Pairing'] == qs['Pairing'][i], 'pair_id'] = curr_id
                # qs.at[qs['Pairing'] == qs['Pairing'][i], 'forced_pair'] = True
                curr_id += 1

    for i in range(len(qs)):
        if qs.pair_id[i] != -1:
            bool_arr = qs.pair_id == qs.pair_id[i]
            average = np.mean(qs.Difficulty[bool_arr])
            for j in range(len(bool_arr)):
                if bool_arr[j]:
                    qs.at[j, "new_diff"] = average
            rand_num = rand(qs.new_diff[i])
            for j in range(len(bool_arr)):
                if bool_arr[j]:
                    qs.at[j, "new_diff"] = rand_num

        # qs.at[qs.pair_id == qs.pair_id[i], 'new_diff'] = np.mean(
        # qs.Difficulty[qs.pair_id == qs.pair_id[i]])
        # qs.at[qs.pair_id == qs.pair_id[i], 'new_diff'] = rand(qs.new_diff[i])
        else:
            qs.at[i, "new_diff"] = qs.Difficulty[i]
            qs.at[i, "new_diff"] = rand(qs.new_diff[i])

    ##    qs.insert(len(qs.columns), 'backup_diff', qs.new_diff)

    # looks at question quality
    while np.count_nonzero(qs.round_number != -1) > 2 * target:
        rem = [
            np.count_nonzero(
                np.logical_and(qs.round_number != -1, qs.is_bonus == i)
            )  # number of questions remaining of specific type
            for i in range(2)
        ]
        assert rem[0] >= target and rem[1] >= target
        i = int(rem[1] > rem[0])
        if rem[1 - i] > target:
            candidates = (qs.round_number != -1) & (qs.is_bonus == i)
            min_q = min(qs.Quality[candidates])
            choice = np.random.choice(np.where(candidates & (qs.Quality == min_q))[0])
            if qs.pair_id[choice] != -1:
                qs.at[qs.pair_id == qs.pair_id[choice], "round_number"] = -1
            else:
                qs.at[choice, "round_number"] = -1
        else:
            candidates = (
                (qs.round_number != -1) & (qs.is_bonus == i) & (qs.pair_id == -1)
            )
            min_q = min(qs.Quality[candidates])
            choice = np.random.choice(np.where(candidates & (qs.Quality == min_q))[0])
            qs.at[
                choice, "round_number"
            ] = -1  # sets round numbers to -1 for removed questions

    qs.sort_values("new_diff", inplace=True, ignore_index=True)

    t = 0
    b = 0
    while t < len(qs) and b < len(qs):
        if (qs.round_number[t] == -1) or (qs.is_bonus[t] != 0) or (qs.pair_id[t] != -1):
            t += 1
            continue
        if (qs.round_number[b] == -1) or (qs.is_bonus[b] != 1) or (qs.pair_id[b] != -1):
            b += 1
            continue
        qs.at[t, "pair_id"] = curr_id
        qs.at[b, "pair_id"] = curr_id
        # print(qs, t, b)
        # print(qs.at[b, 'Question'])
        new_difference = (qs.new_diff[t] + qs.new_diff[b]) / 2

        qs.at[t, "new_diff"] = new_difference
        qs.at[b, "new_diff"] = new_difference
        curr_id += 1

    ##    for i in range(len(qs)):
    ##        if qs.pair_id[i] != -1:
    ##            qs.at[i, 'new_difficulty'] = np.mean(
    ##                qs.Difficulty[qs.pair_id == qs.pair_id[i]])
    ##        else:
    ##            qs.at[i, 'new_difficulty'] = qs.Difficulty[i]

    qs.sort_values(
        ["round_number", "new_diff", "pair_id", "is_bonus"],
        ascending=[False, True, True, True],
        inplace=True,
        ignore_index=True,
    )

    qs.insert(len(qs.columns), "rr_order", -1)
    perm = np.arange(round_robin * per_round)
    np.random.shuffle(perm)
    for i in range(round_robin * per_round):
        qs.at[2 * i, "rr_order"] = perm[i]
        qs.at[2 * i + 1, "rr_order"] = perm[i]

    qs.sort_values(
        ["round_number", "rr_order", "new_diff", "pair_id", "is_bonus"],
        ascending=[False, False, True, True, True],
        inplace=True,
        ignore_index=True,
    )

    ##    qs.insert(len(qs.columns), 'packet_order', 1000)
    ##
    for i in range(num_rounds):
        for j in range(i * per_round * 2, (i + 1) * per_round * 2):
            qs.at[j, "round_number"] = i + 1
        # qs.at[i*per_round*2:(i+1)*per_round*2-1, 'round_number'] = i+1

    ##        for j in range(per_round):
    ##            qs.at[i*per_round*2+j*2:i*per_round*2+j*2+1,
    ##                  'packet_order'] = 10*i+j+np.random.uniform()

    qs.rename(columns={"round_number": "Round"}, inplace=True)

    set_packet_order(qs, per_round)

    qs.drop(columns=["rr_order", "is_bonus", "new_diff", "pair_id"], inplace=True)

    return qs


def set_packet_order(qs, per_round):
    if "packet_order" in qs.columns:
        qs.packet_order = 1000
    else:
        qs.insert(len(qs.columns), "packet_order", 1000)
    for i in range(num_rounds):
        assert all(
            qs.loc[i * per_round * 2 : (i + 1) * per_round * 2 - 1, "Round"] == i + 1
        ), qs.Category[0]
        for j in range(per_round):
            val = 10 * i + j + np.random.uniform()
            for k in range(i * per_round * 2 + j * 2, i * per_round * 2 + j * 2 + 2):
                qs.at[k, "packet_order"] = val
            # qs.at[i*per_round*2+j*2:i*per_round*2+j*2+1,
            #'packet_order'] = 10*i+j+np.random.uniform()
    for i in range(num_tb):
        row = np.where(qs.Round == i + 20)[0]
        assert len(row) <= 1
        if len(row) == 1:
            qs.at[row, "packet_order"] = 10 * (i + 20) + np.random.uniform()


def interleave(qs_list):
    all_qs = pd.concat(qs_list, ignore_index=True)
    all_qs.sort_values(
        ["packet_order", "Toss up/Bonus"],
        ascending=[True, False],
        inplace=True,
        ignore_index=True,
    )
    return all_qs


def gen_tex(rnd, round_number):
    out = []
    i = 0
    for _, row in rnd.iterrows():
        if i % 2 == 0:
            out.append("\\filbreak")
        out.append(
            "\\question{%s}{%s}{%s}{%s}{%s}{%s}\n"
            % (
                i // 2 + 1,
                row["Toss up/Bonus"],
                row["Category"],
                row["Type"],
                texify(row["Question"]),
                texify(row["Answer"]),
            )
        )
        if i % 2 == 1:
            out.append("\\hrulefill")
        i += 1
    return ("\\newcommand{\\roundnumber}{%d}" % round_number) + (
        ROUND_TEMPLATE % "\n".join(out)
    )


def gen_tex_tb(rnd, round_number):
    out = []
    i = 0
    for _, row in rnd.iterrows():
        out.append("\\filbreak")
        out.append(
            "\\question{%s}{%s}{%s}{%s}{%s}{%s}\n"
            % (
                i + 1,
                row["Toss up/Bonus"],
                row["Category"],
                row["Type"],
                texify(row["Question"]),
                texify(row["Answer"]),
            )
        )

        out.append("\\hrulefill")
        i += 1

    # if round_number == 5:
    #     print('\n'.join(out))

    return ("\\newcommand{\\roundnumber}{%d}" % round_number) + (
        ROUND_TEMPLATE_TB % "\n".join(out)
    )


with open("round_template_python.tex") as f:
    ROUND_TEMPLATE = f.read()

with open("round_template_tb_python.tex") as f:
    ROUND_TEMPLATE_TB = f.read()

if not os.path.exists("splitrounds"):
    os.mkdir("splitrounds")

if not os.path.exists("categories"):
    os.mkdir("categories")

if len(sys.argv) == 1:
    sys.argv += [f"categories/Prepacket - {c}.csv" for c in categories]
    # sys.argv += ['Combined questions raw - Sheet1.csv']

if len(sys.argv) <= 6:
    fname = sys.argv[1]
    all_qs = pd.read_csv(fname)
    if "Round" not in all_qs.columns:
        qs_list = get_data(fname)
        for i in range(len(categories)):
            qs_list[i] = assign(qs_list[i])
            # qs_list[i] = assign(qs_list[i], rand)
            qs_list[i].to_csv("categories/" + categories[i] + ".csv", index=False)
        all_qs = interleave(qs_list)
        all_qs.to_csv("All.csv", index=False)
else:
    qs_list = [pd.read_csv(fname) for fname in sys.argv[1:]]
    for i in range(6):
        set_packet_order(qs_list[i], category_targets[i])
    all_qs = interleave(qs_list)
    all_qs.to_csv("All.csv", index=False)

rounds = [all_qs[all_qs.Round == i + 1] for i in range(num_rounds)]
for i in range(num_rounds):
    rounds[i].drop(columns=["Round"], inplace=True)
    rounds[i].to_csv(f"splitrounds/round{i+1}.csv", index=False)
    with open(f"splitrounds/round{i+1}.tex", "w") as round_writer:
        round_writer.write(gen_tex(rounds[i], i + 1))

# tb_rounds = [all_qs[all_qs.Round == i+20] for i in range(num_rounds)]
tb_rounds = [all_qs[all_qs.Round == i + 20] for i in range(1, num_tb + 1)]
for i in range(num_tb):
    tb_rounds[i].drop(columns=["Round"], inplace=True)
    rounds[i].to_csv(f"splitrounds/tbround{i+1}.csv", index=False)
    with open(f"splitrounds/tbround{i+1}.tex", "w") as round_writer:
        round_writer.write(gen_tex_tb(tb_rounds[i], i + 1))

# rounds = [all_qs[all_qs.Round == i+1] for i in range(num_rounds)]
# for i in range(num_rounds):
#     rounds[i].drop(columns=['Round'], inplace=True)
#     rounds[i] = rounds[i].applymap(lambda s: '{{{}}}'.format(s))
# ##    rounds[i].to_csv(f'splitrounds/round{i+1}.csv', index=False,
# ##                     quoting=csv.QUOTE_NONE)
#     with open('splitrounds/round{}.csv'.format(i+1), 'w') as round_writer:
#         round_writer.write(','.join(rounds[i].columns) + '\n')
#         for _, row in rounds[i].iterrows():
#             round_writer.write(','.join(row) + '\n')
#
# tb_rounds = [all_qs[all_qs.Round == i+20] for i in range(num_rounds)]
# for i in range(num_tb):
#     tb_rounds[i].drop(columns=['Round'], inplace=True)
#     tb_rounds[i] = tb_rounds[i].applymap(lambda s: '{{{}}}'.format(s))
# ##    rounds[i].to_csv(f'splitrounds/round{i+1}.csv', index=False,
# ##                     quoting=csv.QUOTE_NONE)
#     with open('tiebreaks/tbround{}.csv'.format(i+1), 'w') as round_writer:
#         round_writer.write(','.join(tb_rounds[i].columns) + '\n')
#         for _, row in tb_rounds[i].iterrows():
#             round_writer.write(','.join(row) + '\n')
