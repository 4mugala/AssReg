from PySide6.QtCore import QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QStyledItemDelegate, QStyle


import pandas as pd

from PySide6.QtCore import (
    QModelIndex,
    QAbstractListModel,
    Qt,
    Signal
)


class ListModel(QAbstractListModel):

    data_changed = Signal(pd.DataFrame)

    LOCATION_COLUMNS = {
        "Room",
        "Allocation"
    }

    def __init__(self, data=None, parent=None):
        super().__init__(parent)

        self.df = pd.DataFrame()

        if data is not None:
            self.set_data(data)

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
    # REPLACE DATA
    # =========================================================

    def set_data(self, data):

        new_df = self._to_dataframe(data)

        self.beginResetModel()

        self.df = new_df.reset_index(drop=True)

        self.endResetModel()

        # Notify listeners
        self.data_changed.emit(self.df.copy())

    # =========================================================
    # ADD / UPDATE DATA
    # =========================================================

    def add_data(self, data):

        new_df = self._to_dataframe(data)

        if new_df.empty:
            return

        # -----------------------------------------------------
        # Empty model
        # -----------------------------------------------------

        if self.df.empty:

            new_df = (
                new_df
                .drop_duplicates(keep="last")
                .reset_index(drop=True)
            )

            if new_df.empty:
                return

            self.beginResetModel()

            self.df = new_df

            self.endResetModel()

            self.data_changed.emit(self.df.copy())

            return

        # -----------------------------------------------------
        # Ensure same columns
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
        # Device identity columns
        # -----------------------------------------------------

        device_columns = [
            column
            for column in all_columns
            if column not in self.LOCATION_COLUMNS
        ]

        changed = False

        # -----------------------------------------------------
        # Process incoming rows
        # -----------------------------------------------------

        for _, new_row in new_df.iterrows():

            mask = pd.Series(
                True,
                index=self.df.index
            )

            for column in device_columns:

                old_value = self.df[column]
                new_value = new_row[column]

                if pd.isna(new_value):
                    mask &= old_value.isna()
                else:
                    mask &= old_value.eq(new_value)

            matches = self.df.index[mask]

            # -------------------------------------------------
            # New device
            # -------------------------------------------------

            if len(matches) == 0:

                row_position = len(self.df)

                self.beginInsertRows(
                    QModelIndex(),
                    row_position,
                    row_position
                )

                self.df.loc[len(self.df)] = new_row

                self.endInsertRows()

                changed = True

                continue

            # -------------------------------------------------
            # Existing device
            # -------------------------------------------------

            existing_index = matches[0]

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

            # -------------------------------------------------
            # Exact duplicate
            # -------------------------------------------------

            if same:
                continue

            # -------------------------------------------------
            # Existing device has changed
            # -------------------------------------------------

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

            changed = True

        # -----------------------------------------------------
        # Notify external listeners only if data changed
        # -----------------------------------------------------

        if changed:
            self.data_changed.emit(
                self.df.copy()
            )

    # =========================================================
    # GET DATA
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
