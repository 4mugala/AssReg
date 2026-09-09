import pandas as pd

from PySide6.QtCore import QModelIndex, QAbstractListModel, QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QStyledItemDelegate, QStyle

import pandas as pd

from PySide6.QtCore import (
    QModelIndex,
    QAbstractListModel,
    Qt
)


class ListModel(QAbstractListModel):
    # Columns that are NOT used to identify a duplicate
    LOCATION_COLUMNS = {
        "Room",
        "Allocation"
    }

    def __init__(self, data=None, parent=None):
        super().__init__(parent)

        self.df = pd.DataFrame()

        if data is not None:
            self.set_data(data)

    # =========================================================
    # Convert input to DataFrame
    # =========================================================

    @staticmethod
    def _to_dataframe(data):

        if isinstance(data, pd.DataFrame):
            return data.copy()

        if isinstance(data, list):

            if not all(isinstance(item, dict) for item in data):
                raise TypeError(
                    "List data must contain dictionaries."
                )

            return pd.DataFrame(data)

        raise TypeError(
            "Data must be either a pandas DataFrame "
            "or a list of dictionaries."
        )

    # =========================================================
    # Qt Model
    # =========================================================

    def rowCount(self, parent=QModelIndex()):

        if parent.isValid():
            return 0

        return len(self.df)

    def data(self, index, role=Qt.DisplayRole):

        if not index.isValid():
            return None

        row = index.row()

        if row < 0 or row >= len(self.df):
            return None

        if role == Qt.DisplayRole:
            return self.df.iloc[row].to_dict()

        return None

    # =========================================================
    # SET / REPLACE ALL DATA
    # =========================================================

    def set_data(self, data):
        """
        Replace all existing model data.

        data can be:
            - pandas.DataFrame
            - list of dictionaries
        """

        new_df = self._to_dataframe(data)

        self.beginResetModel()

        self.df = new_df.reset_index(drop=True)

        self.endResetModel()

    # =========================================================
    # ADD / UPDATE DATA
    # =========================================================

    def add_data(self, data):
        """
        Add devices to the model.

        Duplicate handling:

        - Device does not exist:
              Add it.

        - Device exists and Room/Allocation changed:
              Replace the existing row.

        - Device exists and nothing changed:
              Do nothing.

        data can be:
            - pandas.DataFrame
            - list of dictionaries
        """

        new_df = self._to_dataframe(data)

        if new_df.empty:
            return

        # -----------------------------------------------------
        # If model is empty
        # -----------------------------------------------------

        if self.df.empty:
            new_df = new_df.drop_duplicates(
                keep="last"
            ).reset_index(drop=True)

            self.beginResetModel()

            self.df = new_df

            self.endResetModel()

            return

        # -----------------------------------------------------
        # Make sure both DataFrames have the same columns
        # -----------------------------------------------------

        all_columns = list(
            dict.fromkeys(
                list(self.df.columns) +
                list(new_df.columns)
            )
        )

        self.df = self.df.reindex(
            columns=all_columns
        )

        new_df = new_df.reindex(
            columns=all_columns
        )

        # -----------------------------------------------------
        # Columns used to identify a device
        # -----------------------------------------------------

        device_columns = [
            column
            for column in all_columns
            if column not in self.LOCATION_COLUMNS
        ]

        # -----------------------------------------------------
        # Process each incoming device
        # -----------------------------------------------------

        for _, new_row in new_df.iterrows():

            # Find matching device(s)
            mask = pd.Series(
                True,
                index=self.df.index
            )

            for column in device_columns:

                old_value = self.df[column]
                new_value = new_row[column]

                # Handle NaN == NaN
                if pd.isna(new_value):

                    mask &= old_value.isna()

                else:

                    mask &= old_value.eq(new_value)

            matches = self.df.index[mask]

            # =================================================
            # DEVICE DOES NOT EXIST
            # =================================================

            if len(matches) == 0:
                row_position = len(self.df)

                self.beginInsertRows(
                    QModelIndex(),
                    row_position,
                    row_position
                )

                self.df.loc[
                    len(self.df)
                ] = new_row

                self.endInsertRows()

                continue

            # =================================================
            # DEVICE ALREADY EXISTS
            # =================================================

            existing_index = matches[0]

            # Check whether the complete row is identical
            existing_row = self.df.loc[
                existing_index
            ]

            same = True

            for column in all_columns:

                old_value = existing_row[column]
                new_value = new_row[column]

                if pd.isna(old_value) and pd.isna(new_value):
                    continue

                if old_value != new_value:
                    same = False
                    break

            # =================================================
            # EXACT DUPLICATE
            # =================================================

            if same:
                # Nothing to do
                continue

            # =================================================
            # DEVICE EXISTS BUT DATA CHANGED
            # =================================================

            row_position = self.df.index.get_loc(
                existing_index
            )

            self.df.loc[
                existing_index,
                all_columns
            ] = new_row[all_columns].values

            index = self.index(row_position)

            self.dataChanged.emit(
                index,
                index,
                [Qt.DisplayRole]
            )

    # =========================================================
    # Get DataFrame
    # =========================================================

    def get_dataframe(self):

        return self.df.copy()


class ItemDelegate(QStyledItemDelegate):
    ITEM_HEIGHT = 80

    local_serial_numbers = []

    def paint(self, painter, option, index):

        item = index.data(Qt.DisplayRole)

        if not item:
            return

        painter.save()

        # -----------------------------------------------------
        # Background
        # -----------------------------------------------------

        if option.state & QStyle.State_Selected:

            painter.fillRect(
                option.rect,
                option.palette.highlight()
            )

            text_color = (
                option.palette.highlightedText().color()
            )

        else:

            text_color = option.palette.text().color()

        painter.setPen(text_color)

        # -----------------------------------------------------
        # Coordinates
        # -----------------------------------------------------

        x = option.rect.left() + 16
        y = option.rect.top() + 10

        # -----------------------------------------------------
        # Device Name
        # -----------------------------------------------------

        name_font = QFont(option.font)
        name_font.setBold(True)
        name_font.setPointSize(11)

        painter.setFont(name_font)

        painter.drawText(
            x,
            y + 15,
            str(item.get("Device Name", "Unknown"))
        )

        # -----------------------------------------------------
        # Serial Number
        # -----------------------------------------------------

        normal_font = QFont(option.font)
        normal_font.setPointSize(11)

        painter.setFont(normal_font)

        serial_number = item.get(
            "Serial Number",
            ""
        )

        painter.drawText(
            x,
            y + 36,
            f"Serial Number: {serial_number}"
        )

        # -----------------------------------------------------
        # Node
        # -----------------------------------------------------

        node = "Unknown"

        if self.local_serial_numbers:
            node = (
                "Local"
                if serial_number in self.local_serial_numbers
                else "Remote"
            )

        node_font = QFont(option.font)
        node_font.setPointSize(10)

        painter.setFont(node_font)

        painter.drawText(
            x,
            y + 57,
            f"Node: {node}"
        )

        painter.restore()

    def sizeHint(self, option, index):

        return QSize(
            0,
            self.ITEM_HEIGHT
        )
