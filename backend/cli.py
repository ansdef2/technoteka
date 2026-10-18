"""Приглашения из командной строки (то же можно сделать в админке):

    python -m backend.cli invite "НИИ Пример" ai,manual
    python -m backend.cli invites
"""
import sys

from backend import db
from backend.main import list_invites, make_invite


def main(argv):
    db.init()
    if len(argv) >= 2 and argv[0] == "invite":
        plan = (argv[2] if len(argv) > 2 else "ai").split(",")
        print(make_invite(argv[1], plan))
    elif argv[:1] == ["invites"]:
        for i in list_invites():
            print(f"{i['id']:>3}  {i['org_label']:<30} {','.join(i['plan']):<10} карточек: {i['cards']}  {i['url']}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
