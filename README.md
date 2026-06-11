# NhomConTraiMeoMeo_K24_KDL

Bộ mã đã được tách thành nhiều file nhỏ để dễ kiểm tra, sửa chữa, bảo trì và mở rộng. Ứng dụng giải **Bài toán Quy hoạch tuyến tính** bằng **Python + Tkinter**, giúp bạn nhập bài toán trực quan, theo dõi từng bước **đơn hình**, đồng thời hỗ trợ **trực quan hóa bài toán 2D/3D** và **xuất lời giải ra file .txt** hoặc **HTML**.

---

---

## I. Giới thiệu

### 1. Thành viên nhóm

| Họ và tên | MSSV | Lớp |
|---|---:|---|
| Nguyễn Đăng Nhân | 24280038 | 24KDL1 |
| Lê Tự Phong | 24280039 | 24KDL1 |
| Trần Nguyên Hưng | 24280048 | 24KDL1 |
| Vương Thành Đạt | 24280058 | 24KDL1 |
| Trương Đình Hưng | 24280068 | 24KDL1 |



### 2. Mục đích phần mềm

Phần mềm được xây dựng nhằm mục tiêu giải và minh họa từng bước quá trình giải bài toán Quy hoạch tuyến tính (Linear Programming) tổng quát theo Phương pháp Đơn hình (Simplex Method), phục vụ nhu cầu học tập và giảng dạy.

Các mục tiêu cụ thể:
- Hỗ trợ người dùng nhập bài toán LP tổng quát (tối đa/tối thiểu, ràng buộc ≤/≥/=, biến dương/âm/tự do) qua giao diện đồ họa trực quan.
- Tự động chuẩn hóa bài toán về dạng từ điển (dictionary form) và thực hiện thuật toán Simplex với giải thích chi tiết từng bước xoay (pivot).
- Tự động lựa chọn chiến lược giải phù hợp (Dantzig, Bland, Hai pha) dựa trên cấu trúc bài toán, và hiển thị lời khuyên so sánh cho người học.
- Xuất kết quả ra nhiều định dạng (văn bản, HTML có công thức LaTeX, CSV) và cung cấp trực quan hóa hình học (2D và 3D).
- Đóng vai trò công cụ hỗ trợ giảng dạy: giảng viên có thể dùng trực tiếp trên lớp để minh họa, sinh viên dùng để tự kiểm tra bài tập.

### 3. Các chức năng chính của chương trình và thuật toán

Phần mềm được thiết kế với giao diện thân thiện, tập trung vào khả năng tương tác và hỗ trợ giải thuật chi tiết. Các chức năng chính bao gồm:

- Nhập liệu:
  - Nhập số biến (1–5) và số ràng buộc (1–10) qua spinner; bảng nhập liệu tự sinh động.
  - Hỗ trợ ba loại dấu ràng buộc: ≤, ≥, =.
  - Hỗ trợ ba loại dấu biến: ≥ 0, ≤ 0, tự do.
  - Hỗ trợ nhập hệ số dạng phân số (ví dụ 1/2, 3/4) hoặc số thập phân; toàn bộ tính toán nội bộ dùng kiểu Fraction (số hữu tỉ chính xác tuyệt đối).
  - Nhập/xuất bài toán qua file CSV theo định dạng chuẩn riêng.
  - Tích hợp 9 bài toán mẫu (demo preset) sẵn có để điền tự động.

- Chuẩn hóa bài toán:
  - Biến ≤ 0: thay x = −y, y ≥ 0.
  - Biến tự do: thay x = a − b, a, b ≥ 0.
  - Bài toán max: nhân (-1) hàm mục tiêu, đưa về dạng min.
  - Ràng buộc ≥: nhân (-1) để đưa về ≤.
  - Ràng buộc =: tách thành hai ràng buộc ≤ (hướng thuận và nghịch).
  - Thêm biến bù (slack/surplus) cho từng ràng buộc ≤.
  - Xây dựng từ điển (dictionary) khởi đầu.

- Các thuật toán:
  - Phần mềm triển khai ba chiến lược, chạy song song (multi-thread) để so sánh:
    - Simplex Dantzig: áp dụng khi tất cả bi ≥ 0, không có ràng buộc =; chọn biến vào có hệ số âm nhỏ nhất.
    - Simplex Bland: áp dụng khi tất cả bi ≥ 0, có nguy cơ xoay vòng; chọn biến vào/ra có chỉ số nhỏ nhất; đảm bảo hữu hạn.
    - Hai pha: áp dụng khi tồn tại bi < 0 hoặc có ràng buộc =; Pha 1 tìm cơ sở khả thi; Pha 2 tối ưu hóa.
  - Phần mềm tự động phát hiện và xử lý:
    - Xoay vòng (cycling): phát hiện qua lưu chữ ký trạng thái (state signature); nếu Dantzig xoay vòng ở Pha 2 thì tự động fallback sang Bland.
    - Suy biến (degeneracy): đếm và thông báo số bước suy biến (θ = 0).
    - Không giới nội (unbounded): phát hiện khi không tìm được biến ra.
    - Vô số nghiệm (multiple optimal): phát hiện khi có biến không cơ sở với hệ số 0 trên hàm mục tiêu; trình bày nghiệm tổng quát theo tham số.
    - Vô nghiệm (infeasible): phát hiện khi giá trị bổ trợ sau Pha 1 > 0.

- Hiển thị lời giải:
  - In bài toán gốc và toàn bộ quá trình chuẩn hóa.
  - In từng bảng từ điển trước và sau mỗi bước xoay, với highlight màu: cột biến vào (vàng nhạt), hàng biến ra (xanh lam nhạt), ô phần tử xoay (xanh đậm).
  - Giải thích tường minh lý do chọn biến vào (Dantzig/Bland), bảng tỉ số θ, phần tử xoay.
  - Kết luận cuối: trạng thái bài toán, giá trị tối ưu, nghiệm tối ưu (kể cả nghiệm tổng quát nếu vô số nghiệm).
  - Hiển thị khuyến nghị phương pháp phù hợp và cho phép chuyển đổi xem lời giải theo từng phương pháp.

- Xuất kết quả:
  - Xuất .txt: nội dung toàn bộ lời giải dạng văn bản thuần.
  - Xuất HTML: trang web có định dạng đẹp với công thức LaTeX (KaTeX), bảng từ điển có màu highlight, thanh tiến trình, tự mở trình duyệt mặc định.
  - Xuất/Nhập CSV: lưu và tải lại bài toán (không phải lời giải).

- Trực quan hóa hình học:
  - 2D (2 biến): vẽ miền chấp nhận được, các đường biên ràng buộc, đường đồng mức hàm mục tiêu, đánh dấu tất cả đỉnh và điểm tối ưu. Hỗ trợ pan (kéo chuột) và zoom (lăn chuột / nút).
  - 3D (3 biến): vẽ các mặt phẳng ràng buộc và vùng khả thi trong không gian 3 chiều (module viz3d.py, dùng matplotlib 3D).

- Hiện từ điển từng bước:
  - Module animator.py cung cấp cửa sổ popup riêng, hiển thị bảng từ điển Simplex dưới dạng bảng ô màu sắc (như trình chiếu slide), với nút điều hướng Trước/Sau, tự động highlight biến vào/ra/ô xoay ở từng bước. Hỗ trợ cả bài toán một pha và hai pha (phân chia theo nhãn Pha 1/Pha 2).


---

## II. Đánh giá

### 1. Các trường hợp chương trình giải được

Phần mềm đã được hoàn thiện để giải và minh họa đầy đủ các tình huống điển hình của bài toán Quy hoạch tuyến tính, từ những bài toán cơ bản đến những trường hợp đặc biệt cần xử lý cẩn thận.

#### 1.1 Các trường hợp tối ưu cơ bản
- **Tối ưu duy nhất**: chương trình xác định đúng nghiệm duy nhất và giá trị hàm mục tiêu tối ưu.
- **Vô số nghiệm**: phát hiện khi bài toán có nhiều phương án tối ưu và trình bày nghiệm tổng quát theo tham số.
- **Không giới nội**: nhận diện khi hàm mục tiêu có thể giảm hoặc tăng mãi mà không bị chặn trên miền khả thi.
- **Vô nghiệm**: phát hiện khi hệ ràng buộc không thể thỏa mãn đồng thời, kể cả khi cần sử dụng Pha 1 bổ trợ.

#### 1.2 Độ chính xác và tính học thuật
- **Giải đúng và đầy đủ** các trường hợp trên, cả khi không cần Pha 1 lẫn khi cần Pha 1 bổ trợ $x_0$.
- **Chính xác tuyệt đối** nhờ dùng kiểu dữ liệu Fraction, giúp tránh sai số làm tròn như các công cụ dùng số thực kiểu float.
- **Hỗ trợ nhập phân số** như $\frac{1}{2}$, $\frac{3}{4}$, phù hợp với các ví dụ trong sách giáo khoa và bài tập thực hành.

#### 1.3 Minh họa từng bước giải thích rõ ràng
- Không chỉ đưa ra đáp án, mà còn trình bày đầy đủ từng bước giải:
  - lý do chọn biến vào;
  - lý do chọn biến ra;
  - bảng tỉ số $\theta$;
  - phần tử xoay;
  - bảng từ điển trước và sau mỗi bước xoay.
- Nội dung này rất phù hợp để dùng trong giảng dạy và hỗ trợ người học hiểu bản chất thuật toán đơn hình.

#### 1.4 Xử lý các tình huống đặc biệt
- **Xoay vòng (cycling)**: phát hiện bằng cách lưu chữ ký trạng thái, sau đó tự động chuyển từ chiến lược Dantzig sang Bland để tránh vòng lặp vô hạn.
- **Suy biến (degeneracy)**: nhận diện và thông báo các bước có $\theta = 0$.
- **Vô số nghiệm**: phát hiện khi có biến không cơ sở với hệ số bằng 0 trên hàm mục tiêu và trình bày nghiệm tổng quát.

#### 1.5 Tính năng hỗ trợ học tập và so sánh
- **Trực quan hóa hình học** đúng và đẹp cho bài toán 2 biến, kể cả trường hợp miền không bị chặn.
- **Giao diện chuyên nghiệp** với palette màu Nordic Frost nhất quán, hiệu ứng hover, phím tắt và hỗ trợ cuộn chuột trong bảng nhập liệu lớn.
- **Xuất HTML chất lượng cao**: sử dụng KaTeX để render công thức, có highlight bảng và tương thích với nhiều trình duyệt.
- **Chạy đa luồng**: các chiến lược Dantzig và Bland có thể chạy song song, giúp so sánh và hiển thị kết quả ngay lập tức.

### 2. Những chức năng phần mềm mang lại cho người dùng

- Giao diện nhập liệu rõ ràng, chia khối hợp lý;
- Nút điền ví dụ giúp kiểm thử nhanh;
- Nút chạy giải thuật cho ra lời giải từng bước;
- Lời giải hiển thị trong khung riêng;
- Nút xuất file giúp lưu kết quả ra `.txt` để nộp bài, đối chiếu hoặc in ấn;
- Nút xem báo cáo HTML
- Chức năng trực quan hóa giúp người học hiểu hình học của bài toán 2 biến và 3 biến:
  - miền chấp nhận được;
  - các ràng buộc;
  - các đường đồng mức của hàm mục tiêu;
  - điểm tối ưu trên miền nghiệm.

### 3. Đánh giá tổng quan

#### Ưu điểm
- Hiển thị toàn bộ quá trình chuẩn hóa, bao gồm biến đổi tường minh từng ràng buộc và từng biến, không chỉ kết quả cuối.
- Nghiệm tổng quát cho trường hợp vô số nghiệm: trình bày dạng tham số và tính khoảng giá trị hợp lệ của tham số.
- Animator — chức năng hiếm thấy ở các công cụ LP tự do: phát lại từng bảng từ điển như slideshow có màu sắc.
- Tự động đề xuất phương pháp dựa trên cấu trúc bài toán, kèm giải thích lý do.
- Tất cả trong một file thực thi: không cần kết nối mạng, không cần tài khoản, không có quảng cáo.

#### Hạn chế
- Hạn chế về quy mô: số biến bị giới hạn tối đa 5, số ràng buộc tối đa 10. Bài toán thực tế với hàng chục hoặc hàng trăm biến không thể giải được.
- Trực quan hóa chỉ hỗ trợ 2 và 3 biến; từ 4 biến trở lên không có đồ thị.
- Hạn chế về thuật toán: còn thiếu thuật toán đối ngẫu (so với phạm vi kiến thức đã được học, tuy nhiên đã giải quyết được hết các trường hợp của bài toán quy hoạch tuyến tính).
- Trong Pha 1 bổ trợ, khi biến ra được chọn để xoay mà có nhiều hàng cùng tỉ số $\theta$ nhỏ nhất, phần mềm ưu tiên chọn hàng chứa $x_0$ nếu có. Lý do là nếu chọn $x_0$ ra khỏi cơ sở thì $\delta = x_0 = 0$, Pha 1 kết thúc và chuyển sang Pha 2. Ngược lại, nếu chọn một biến khác ra thay vì $x_0$ (dù vẫn hợp lệ về mặt toán học vì $x_0 = 0$), từ từ điển tiếp theo có thể đã tối ưu theo hàm bổ trợ $\delta$ nhưng $x_0$ vẫn còn trong cơ sở với giá trị 0 — lúc đó thuật toán dễ kết luận nhầm là vô nghiệm. Hiện tại phần mềm xử lý đúng trường hợp này, nhưng chưa hiển thị giải thích rõ lý do ưu tiên $x_0$ trong tie-breaking cho người học. Đây là điểm có thể bổ sung thêm phần chú thích trong lời giải.
- Một số trường hợp xử lý chưa hoàn toàn trơn tru: trực quan hóa 3D còn hạn chế trong một số cấu hình miền khả thi phức tạp (polytope nhiều mặt).

---

## III. Chi tiết sử dụng

### 1. Cài đặt và chạy chương trình

Có 2 cách sử dụng chương trình:

#### Cách 1: Chạy file .exe đã đóng gói (dành cho người dùng)

1. Tải file `simplex_app.exe`.
2. Chạy trực tiếp file vừa tải về.
3. Không cần cài Python hay bất kỳ thư viện nào khác.

> Đây là cách thuận tiện nhất nếu bạn chỉ muốn sử dụng chương trình mà không cần chỉnh sửa mã nguồn.

#### Cách 2: Chạy từ mã nguồn (dành cho developer)

1. Clone repository về máy:

```bash
git clone https://github.com/vngthdat206/LinearProgrammingTool_byVC
cd LinearProgrammingTool_byVC

```

2. (Khuyến nghị) Tạo môi trường ảo:

```bash
python -m venv .venv

```

Kích hoạt môi trường ảo phù hợp với hệ điều hành:

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

3. Cài đặt các gói cần thiết từ file `requirements.txt`:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

```

4. Chạy ứng dụng:

```bash
python main.py
```

5. Nếu muốn build lại file `.exe` từ file cấu hình `main.spec`:

```bash
pyinstaller main.spec
```

File output sẽ được tạo tại thư mục `dist/main.exe`.

#### Yêu cầu hệ thống
- Python 3.x
- Thư viện chuẩn `tkinter`
- Môi trường có thể hiển thị cửa sổ đồ họa
- Nếu dùng trực quan hóa 3D, cần cài thêm `matplotlib` và `numpy` (đã được liệt kê trong `requirements.txt`)

---

### 2. Các bước thao tác

Để giải một bài toán Quy hoạch tuyến tính, người dùng thực hiện theo quy trình 5 bước đơn giản dưới đây:

#### Bước 1: Thiết lập bài toán
Ở khung **Thiết lập**, chọn số biến (1–5) và số ràng buộc (1–10). Bảng nhập liệu tự cập nhật.

#### Bước 2: Nhập bài toán
Trong khung **Nhập bài toán**:
- Chọn kiểu bài toán: **max** hoặc **min**.
- Nhập hệ số hàm mục tiêu cho từng biến $x_1, x_2, \dots$
- Chọn dấu của từng biến (**≥ 0**, **≤ 0**, hoặc **tự do**).
- Nhập từng ràng buộc: các hệ số, dấu (**≤ / ≥ / =**), và vế phải.

Có thể dùng phím **Tab** để chuyển giữa các ô, hoặc dùng **cuộn chuột** để xem toàn bộ bảng khi có nhiều ràng buộc.

Ngoài ra, có thể chọn **Nhập CSV** để nhập các bài toán đã được lưu trước đó, hoặc các bài toán mẫu.

Mẹo: Nhấn nút **Điền ví dụ** để tự động điền một trong 9 bài toán mẫu có sẵn, bao gồm các trường hợp: duy nhất nghiệm, vô số nghiệm, không giới nội, vô nghiệm, và xoay vòng. Hoặc nhập CSV với các mẫu test cases ở phụ lục, hoặc các file CSV đã được tải về trước đó (có định dạng phù hợp).

#### Bước 3: Chạy giải thuật
Kiểm tra lại dữ liệu và nhấn nút **Chạy giải thuật (Ctrl+Alt+R)**. Phần mềm sẽ:
- Giải song song bằng cả **Dantzig** và **Bland**.
- Hiển thị khuyến nghị phương pháp phù hợp (**Dantzig / Bland / Hai Pha**) dựa trên cấu trúc bài toán.
- Hiển thị toàn bộ lời giải trong khung **Lời giải** bên phải.

#### Bước 4: Xem lời giải theo phương pháp khác
Ở khung **Tham chiếu Phương pháp giải**, chọn phương pháp muốn xem (**Dantzig / Bland / Hai Pha**) rồi nhấn **Hiển thị lời giải phương pháp đã chọn**. Các phương pháp không phù hợp với bài toán hiện tại sẽ bị mờ.

#### Bước 5: Xuất kết quả
Sau khi có lời giải, các nút sau được kích hoạt:
- **Xuất .txt**: lưu lời giải ra file văn bản.
- **Xem HTML**: hiển thị báo cáo HTML có công thức đẹp và mở trong trình duyệt.
- **Hiện từ vựng**: mở cửa sổ **Animator** để xem lại từng bước xoay.
- **Trực quan hóa**: mở đồ thị **2D (2 biến)** hoặc **3D (3 biến)**.

Ngoài ra, để lưu bài toán lại thì có thể chọn **Xuất CSV**: lưu bài toán hiện tại ra file CSV để dùng lại sau.

---

### 3. Trực quan hóa bài toán

Ứng dụng hỗ trợ hai loại trực quan:

- với **2 biến**: vẽ trực quan hóa 2D.
- với **3 biến**: vẽ trực quan hóa 3D (nếu đã cài `matplotlib` và `numpy`).

Nút hiện thị:
- **Trực quan hóa BT 2 biến** khi số biến = 2
- **Trực quan hóa (3D)** khi số biến = 3

#### Điều kiện để dùng

- Đã nhập đầy đủ hệ số hàm mục tiêu và ràng buộc.
- Nếu số biến khác 2 hoặc 3, chức năng trực quan sẽ không kích hoạt.
- Với 3 biến, cần thư viện `matplotlib` và `numpy` để mở 3D.

#### Kết quả trực quan hóa 2D

Cửa sổ trực quan 2D sẽ hiển thị:
- Các trục tọa độ Oxy;
- Các đường ràng buộc;
- Miền chấp nhận được;
- Các đường đồng mức của hàm mục tiêu;
- Các đỉnh của miền nghiệm;
- Điểm tối ưu.

#### Kết quả trực quan hóa 3D

Cửa sổ trực quan 3D sẽ hiển thị:
- Miền nghiệm trong không gian;
- Mặt phẳng ràng buộc;
- Đỉnh nghiệm khả thi;
- Điểm tối ưu trên miền nghiệm;

#### Tương tác trên cửa sổ trực quan

Người dùng có thể:
- Kéo thả để di chuyển vùng nhìn;
- Dùng chuột để phóng to/thu nhỏ;
- Sử dụng các nút điều khiển trực quan đi kèm.

#### Lưu ý

- Nếu số biến khác 2 hoặc 3, chức năng trực quan sẽ không thực hiện;
- Nếu chưa cài `matplotlib`/`numpy`, trực quan hóa 3D sẽ báo lỗi và đề nghị cài thêm;
- Hình trực quan được thiết kế để phục vụ học tập và quan sát miền nghiệm.

---

### 4. Những lưu ý khi sử dụng

- Nên nhập số hợp lệ, tránh để trống ô quan trọng;
- Với dữ liệu phân số, nên nhập đúng định dạng `a/b`;
- Khi thay đổi số biến hoặc số ràng buộc, nên bấm **Tạo lại bảng nhập** để cập nhật giao diện;
- Sau khi giải xong mới dùng được chức năng xuất file;
- Để xem hình học, chỉ dùng khi số biến là 2 hoặc 3.

---

## IV. Tài liệu tham khảo

1. Phan Quốc Khánh, Trần Tuệ Nương (2002). Giáo trình Quy hoạch tuyến tính. Nhà xuất bản Đại học Quốc gia TP.HCM.
2. Hillier, F. S., & Lieberman, G. J. (2015). Introduction to Operations Research (10th Edition). McGraw-Hill Education.
3. Bazaraa, M. S., Jarvis, J. J., & Sherali, H. D. (2011). Linear Programming and Network Flows. Wiley.
4. Python Software Foundation. Tkinter — Python interface to Tcl/Tk. Truy cập tại: https://docs.python.org/3/library/tkinter.html
5. The Matplotlib Development Team. Matplotlib: Visualization with Python. Truy cập tại: https://matplotlib.org/stable/contents.html
6. GitHub. Linear Programming Tool Repository. Nguồn mã nguồn dự án: https://github.com/vngthdat206/LinearProgrammingTool_byVC
7. Vanderbei, R. J. (2014). Linear Programming: Foundations and Extensions (4th ed.). Springer.
8. Bazaraa, M. S., Jarvis, J. J., & Sherali, H. D. (2010). Linear Programming and Network Flows (4th ed.). Wiley.
9. Bland, R. G. (1977). New finite pivoting rules for the simplex method. Mathematics of Operations Research, 2(2), 103–107.
10. Beale, E. M. L. (1955). Cycling in the dual simplex algorithm. Naval Research Logistics Quarterly, 2(4), 269–275.
11. Tài liệu Python chính thức: fractions.Fraction — https://docs.python.org/3/library/fractions.html
12. KaTeX — Thư viện render LaTeX cho HTML: https://katex.org

---

## Cấu trúc dự án

- `main.py`: điểm chạy chương trình
- `simplex_app.py`: giao diện Tkinter, nhập liệu, điều khiển giải thuật, xuất file và gọi trực quan hóa
- `simplex_engine.py`: thuật toán đơn hình, chuẩn hóa bài toán và xử lý các trường hợp đặc biệt
- `models.py`: định nghĩa các dataclass dùng chung
- `utils.py`: các hàm tiện ích xử lý số và định dạng, trợ giúp in biểu thức
- `html_exporter.py`: xuất lời giải sang HTML đẹp
- `animator.py`: trình chiếu từng bước giải đơn hình, giúp xem lại bảng từ điển và các biến vào/ra một cách trực quan
- `viz3d.py`: trực quan hóa 3D cho bài toán 3 biến
- `reference_original.py`: phiên bản tham khảo/mã gốc không chạy chính
- `requirements.txt`: liệt kê thư viện phụ thuộc
- `__init__.py`: đánh dấu thư mục gói Python

---


### Yêu cầu hệ thống

- Python 3.x
- Tkinter (mặc định trên Windows)
- `matplotlib`, `numpy` để dùng tính năng trực quan hóa 3D
- file `requirements.txt` chứa các thư viện phụ thuộc

