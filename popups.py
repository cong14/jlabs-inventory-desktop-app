from kivy.uix.popup import Popup


# ERROR POPUPS
class LookupErrorPopup(Popup):
    """lookup screen popup when user tries to enter invalid jlab number"""
    pass


class CsvErrorPopup(Popup):
    """ error when you try to save a report without .csv extension """
    pass


class NoSelectionErrorPopup(Popup):
    """on report screen, if you try to generate a report w/o selecting a jab and info  """
    pass


class NoFilenameErrorPopup(Popup):
    """if you try to save a report without entering a file name """
    pass


class ErrorQuotesPopup(Popup):
    """tells user not to use qoutation marks in fields """
    pass


class ErrorResetPopup(Popup):
    """tells users what information was invalid and allows them or either reset info or change it again """
    pass


class ErrorPopup(Popup):
    """general popup, overwritten to meet needs """
    pass


class OwnerScrollPopup(Popup):
    """error when adding an owner """
    pass


# ALERT POPUPS - tell user that changes have been made or that they cannot commit a certain action
class SelOwner(Popup):
    """ on owner popup, you must select an owner to be able to hit select or edit"""
    pass


class EmptyOwner(Popup):
    """owner name cannot be empty when creating new owner """
    pass


class ConfPopup(Popup):
    pass


class InactiveLink(Popup):
    """ alert user that they cannot add a machine to an inactive jlab """
    pass


class SelectJLabPopup(Popup):
    pass


class CheckPopup(Popup):
    """"tell user that they have to have item check on adv lookups in order to look up jlabs or machines """
    pass


class FileCreatedPopup(Popup):
    """notify user that they sucessfully created a file """
    pass


class FilePopup(Popup):
    """popup to save a report file"""
    pass


class ClearSelection(Popup):
    """ Class with flag to allow the popup to clear all selections
    :param: None
    :return: None
    """
    yes = False  # Gets set to True if yes is selected


