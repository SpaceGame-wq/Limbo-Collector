def test_shadowing():
    try:
        x = 1/0
    except Exception:
        print("Capture tout")
    except ZeroDivisionError: # MORTE : Shadowed par Exception
        print("Div par zero")

def test_dead_else():
    try:
        return True
    except ValueError:
        return False
    else:
        print("Je suis mort") # MORTE : car le try return toujours

def test_after_finally():
    try:
        print("test")
    finally:
        return True
    
    print("Inatteignable") # MORTE : car le finally intercepte tout et sort