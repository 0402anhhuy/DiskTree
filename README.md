# 🌳 DiskTree Analyzer

Công cụ phân tích dung lượng ổ đĩa trực quan, giao diện cây thư mục, chạy trên Windows. Hiển thị kích thước, tỷ trọng và số mục con của từng file/thư mục, giúp bạn nhanh chóng tìm ra nơi chiếm nhiều dung lượng nhất.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.6%2B-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Tính năng

- **Quét nhanh** toàn bộ ổ đĩa hoặc bất kỳ thư mục nào
- **Cây thư mục** sắp xếp theo dung lượng giảm dần, giúp xác định "thủ phạm" ngay lập tức
- **Thanh tỷ trọng trực quan** cho thấy phần trăm dung lượng mỗi mục chiếm so với tổng
- **Panel chi tiết** bên phải hiển thị tên, loại, dung lượng, tỷ trọng và đường dẫn đầy đủ
- **Mở trong File Explorer** bằng một click hoặc double-click thẳng trên cây
- Quét chạy ngầm (background thread), UI không bị đứng, có thể dừng giữa chừng
- Bỏ qua symlink/junction point, tránh vòng lặp vô tận trên Windows

---

## Yêu cầu hệ thống

| Thành phần         | Phiên bản tối thiểu |
| ------------------ | ------------------- |
| Python             | 3.10                |
| PySide6-Essentials | 6.6.0               |
| Hệ điều hành       | Windows 10 / 11     |

---

## Cài đặt & Chạy từ source

### 1. Clone repository

```bash
git clone https://github.com/0402anhhuy/DiskTree.git
cd DiskTree
```

### 2. Tạo môi trường ảo (khuyến nghị)

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 4. Chạy ứng dụng

```bash
python main.py
```

---

## Build thành file `.exe` (Standalone)

Dự án đã có sẵn script `build.bat`. Chỉ cần nhấn đúp vào file hoặc chạy:

```bat
build.bat
```

Script sẽ tự động:

1. Tạo môi trường ảo `.venv` nếu chưa có
2. Cài đặt dependencies từ `requirements.txt`
3. Đóng gói thành 1 file `.exe` duy nhất bằng PyInstaller
4. Dọn dẹp file tạm sau khi build

File `.exe` sẽ được xuất ra thư mục `dist/`. Có thể chạy trực tiếp trên máy khác mà không cần cài Python hay PySide6.

> **Lưu ý:** Lần đầu build sẽ mất vài phút do PyInstaller đóng gói toàn bộ runtime.

---

## Hướng dẫn sử dụng

1. **Chọn ổ đĩa** từ dropdown _Ổ đĩa_ hoặc nhấn **Chọn thư mục…** để duyệt đến thư mục bất kỳ. Bạn cũng có thể gõ thẳng đường dẫn vào ô nhập.
2. Nhấn **Quét ngay** — thanh trạng thái phía dưới sẽ cập nhật tiến độ theo thời gian thực.
3. Sau khi quét xong, cây thư mục hiển thị kết quả với **bốn cột**:

    | Cột                | Nội dung                               |
    | ------------------ | -------------------------------------- |
    | Tên File / Thư mục | Tên kèm icon loại file                 |
    | Dung lượng         | Kích thước đã định dạng (KB / MB / GB) |
    | Tỷ trọng (%)       | Thanh progress thể hiện % so với tổng  |
    | Số mục con         | Tổng số file + thư mục bên trong       |

4. **Click** vào bất kỳ dòng nào để xem chi tiết ở panel bên phải.
5. **Double-click** hoặc nhấn **Mở trong File Explorer** để mở thẳng vị trí đó trong Windows Explorer.
6. Nhấn **Dừng** để hủy quét giữa chừng nếu cần.

---

## Cấu trúc project

```
DiskTree/
├── main.py          # Toàn bộ source code ứng dụng
├── requirements.txt # Dependencies (PySide6, PyInstaller)
├── build.bat        # Script build .exe
├── .gitignore
└── LICENSE
```

---

## License

Phát hành theo giấy phép [MIT](LICENSE).
